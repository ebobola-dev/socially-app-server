import asyncio
from datetime import datetime
from functools import wraps
from logging import Logger

from jwt.exceptions import ExpiredSignatureError, PyJWTError
from socketio import AsyncNamespace

from database.database import Database
from models.comment import Comment
from models.sio.authorize_error import AuthorizeError
from models.sio.sio_ack import SioAck
from models.sio.sio_rooms import SioRooms
from models.sio.sio_session import AuthorizedSioSession, SioSession
from repositories.user_repository import UserRepository
from services.tokens_service import TokensService
from utils.serialize_util import serialize_value


def check_authorization(handler):
    @wraps(handler)
    async def wrapper(self, sid, *args, **kwargs):
        session = await self.get_session(sid)
        if not isinstance(session, AuthorizedSioSession):
            self._logger.warning(
                f"[{sid}] Tried to access event without authorization ({handler.__name__})\n"
            )
            return SioAck.failed("You are not authorized").to_json()
        return await handler(self, sid, *args, **kwargs, session=session)

    return wrapper


class SioController(AsyncNamespace):
    def __init__(self, logger: Logger, namespace="/"):
        super().__init__(namespace)
        self._logger = logger
        self._wait_authorization_tasks: dict[str, asyncio.Task] = {}

    async def _wait_authorization(self, sid):
        await asyncio.sleep(60)
        session = await self.get_session(sid)
        if not isinstance(session, AuthorizedSioSession):
            self._logger.info(
                f"[{sid}] Didn't authorize for a minute, disconnecting...\n"
            )
            await self.disconnect(sid)
        self._cancel_wait_authorization(sid)

    def _cancel_wait_authorization(self, sid):
        task = self._wait_authorization_tasks.get(sid)
        if task:
            task.cancel()
            self._wait_authorization_tasks.pop(sid, None)
            self._logger.debug(f"[{sid}] Wait authorization task canceled\n")

    async def _authorize(self, db_session, sid, data) -> AuthorizedSioSession:
        try:
            device_id = data.get("device_id")
            access_token = data.get("access_token")
            if not device_id:
                raise AuthorizeError(
                    internal_message="Didn't specify device id",
                    ack_message="Device id is reqiured",
                )
            if access_token is None:
                raise AuthorizeError(
                    internal_message="Access token is not specified",
                    ack_message="Bad token",
                )
            token_data = TokensService.decode_access(access_token)
            user_id = token_data.get("id")
            user_role = token_data.get("role")
            user = await UserRepository.get_by_id_with_relations(
                session=db_session,
                user_id=user_id,
            )
            if not user:
                raise AuthorizeError(
                    internal_message=f"Access token is valid, but unable to find user with id({user_id})",
                    ack_message="Bad token",
                )
            refresh_token_model = (
                await TokensService.get_refresh_by_user_and_device_ids(
                    session=db_session,
                    user_id=user_id,
                    device_id=device_id,
                )
            )
            if not refresh_token_model:
                raise AuthorizeError(
                    internal_message=f"Access token is valid and user found, but unable to find refresh token in database with device_id({device_id}) and user_id({user_id})",
                    ack_message="Bad token",
                )
            return AuthorizedSioSession(
                sid=sid,
                user_id=user_id,
                user_role=user_role,
                device_id=device_id,
            )
        except ExpiredSignatureError:
            raise AuthorizeError(
                internal_message="Access token has expired",
                ack_message="Token has expired",
            )
        except PyJWTError as decoding_error:
            raise AuthorizeError(
                internal_message=f"Unable to decode access token: {decoding_error}",
                ack_message="Bad token",
            )
        except Exception as unexcepted_error:
            raise AuthorizeError(
                internal_message=f"Unecxecpted error on authorization: {unexcepted_error}"
            )

    # * ------------------------ Event Listeners ------------------------
    async def on_connect(self, sid, environ, auth=None):
        await self.save_session(sid, SioSession(sid))
        self._wait_authorization_tasks[sid] = asyncio.create_task(
            self._wait_authorization(sid)
        )
        self._logger.info(f"[{sid}] Connected, waiting for authorization...\n")

    async def on_disconnect(self, sid, reason):
        async with Database.session_maker() as db_session:
            self._logger.info(f"[{sid}] Disconnected ({reason})\n")
            self._cancel_wait_authorization(sid)
            session: SioSession = await self.get_session(sid)

            # * Set user disconnected
            if isinstance(session, AuthorizedSioSession):
                try:
                    updated_user = await UserRepository.set_current_sid(
                        db_session, session.user_id, new_sid=None
                    )
                    await db_session.commit()
                    await self.emit_user_is_offline(
                        user_id=session.user_id,
                        last_seen=updated_user.last_seen,
                    )
                except Exception as db_error:
                    await db_session.rollback()
                    self._logger.error(
                        f"(on_disconnect) Error on set current sid to user {session.user_id}: {db_error}"
                    )

    async def on_authorize(self, sid, data=None):
        if not data or not isinstance(data, dict):
            return SioAck.failed("Bad authorization data").to_json()
        async with Database.session_maker() as db_session:
            try:
                authorized_session = await self._authorize(
                    db_session=db_session,
                    sid=sid,
                    data=data,
                )
                await self.save_session(sid, authorized_session)
                await UserRepository.set_current_sid(
                    session=db_session,
                    user_id=authorized_session.user_id,
                    new_sid=sid,
                )
                await db_session.commit()
                self._logger.info(f"[{sid}] Successfuly authorized\n")
                self._cancel_wait_authorization(sid)
                await self.enter_room(
                    sid=sid,
                    room=SioRooms.get_authorized_room(),
                )
                await self.enter_room(
                    sid=sid,
                    room=SioRooms.get_personal_room(user_id=authorized_session.user_id),
                )
                return SioAck.success().to_json()
            except AuthorizeError as authorized_error:
                self._logger.error(
                    f"[{sid}] Couldn't authorize: {authorized_error.internal_message}\n"
                )
                return SioAck.failed(authorized_error.ack_message).to_json()
            except Exception as error:
                await db_session.rollback()
                self._logger.error(f"[{sid}] unexcepted error on authorize: {error}\n")
                return SioAck.failed("Something went wrong").to_json()

    @check_authorization
    async def on_put_app_in_background(
        self, sid, data=None, session: AuthorizedSioSession = None
    ):
        self._logger.debug(f"[{sid}] got event (put_app_in_background)\n")

        # * Set user offline
        async with Database.session_maker() as db_session:
            try:
                updated_user = await UserRepository.toggle_online(
                    db_session, session.user_id, False
                )
                await db_session.commit()
                await self.emit_user_is_offline(
                    user_id=session.user_id, last_seen=updated_user.last_seen
                )
                return SioAck.success().to_json()
            except Exception as error:
                self._logger.error(
                    f"(on_put_app_in_background) error on toggle online: {error}"
                )
                await db_session.rollback()
                return SioAck.failed().to_json()

    @check_authorization
    async def on_put_app_in_foreground(
        self, sid, data=None, session: AuthorizedSioSession = None
    ):
        self._logger.debug(f"[{sid}] got event (put_app_in_foreground)\n")
        await self.emit_user_is_online(session.user_id)

        # * Set user online
        async with Database.session_maker() as db_session:
            try:
                await UserRepository.toggle_online(db_session, session.user_id, True)
                await db_session.commit()
                return SioAck.success().to_json()
            except Exception as error:
                self._logger.error(
                    f"(on_put_app_in_background) error on toggle online: {error}"
                )
                await db_session.rollback()
                return SioAck.failed().to_json()

    @check_authorization
    async def on_join_to_post_room(
        self, sid, data: dict | None = None, session: AuthorizedSioSession = None
    ):
        if not isinstance(data, dict):
            return SioAck.failed(error_text="Post id must be specified")
        post_id = data.get("post_id")
        if post_id is None:
            return SioAck.failed(error_text="Post id must be specified")
        await self.enter_room(sid=sid, room=SioRooms.get_post_room(post_id=post_id))
        return SioAck.success()

    @check_authorization
    async def on_leave_from_post_room(
        self, sid, data: dict | None = None, session: AuthorizedSioSession = None
    ):
        if not isinstance(data, dict):
            return SioAck.failed(error_text="Post id must be specified")
        post_id = data.get("post_id")
        if post_id is None:
            return SioAck.failed(error_text="Post id must be specified")
        await self.leave_room(sid=sid, room=SioRooms.get_post_room(post_id=post_id))
        return SioAck.success()

    # * ------------------------ Emitters ------------------------
    async def on_logout(self, user_sid: str | None):
        if user_sid:
            await self.disconnect(user_sid)

    async def on_user_deleted(self, user_sid: str | None):
        if user_sid:
            await self.disconnect(user_sid)

    async def emit_user_is_offline(self, user_id: str, last_seen: datetime):
        await self.emit(
            event="user_is_offline",
            data={"user_id": user_id, "last_seen": serialize_value(last_seen)},
            room=SioRooms.get_authorized_room(),
        )

    async def emit_user_is_online(self, user_id: str):
        await self.emit(
            event="user_is_online",
            data={"user_id": user_id},
            room=SioRooms.get_authorized_room(),
        )

    async def emit_new_follower(
        self,
        target_sid: str | None,
        follower_id: str,
        follower_username: str,
    ):
        if target_sid:
            await self.emit(
                event="new_follower",
                data={
                    "follower_id": follower_id,
                    "follower_username": follower_username,
                },
                to=target_sid,
            )

    async def emit_new_comment(
        self, new_comment: Comment, post_author_sid: str | None = None
    ):
        await self.emit(
            "new_comment",
            data={"new_comment": new_comment.to_json(include_reply=True)},
            room=SioRooms.get_post_room(post_id=new_comment.post_id),
        )
        if post_author_sid:
            await self.emit(
                "new_comment_on_your_post",
                data={"new_comment": new_comment.to_json(include_reply=True)},
                to=post_author_sid,
            )

    async def emit_comment_deleted(
        self,
        post_id: str,
        comment_id: str,
    ):
        await self.emit(
            "comment_deleted",
            data={
                "comment_id": comment_id,
                "post_id": post_id,
            },
            room=SioRooms.get_post_room(post_id=post_id),
        )

    async def emit_post_deleted(
        self,
        post_id: str,
    ):
        await self.emit(
            "post_deleted",
            data={
                "post_id": post_id,
            },
            room=SioRooms.get_post_room(post_id=post_id),
        )

    async def emit_post_likes_count_changed(self, post_id: str, new_likes_count: int):
        await self.emit(
            "post_likes_count_changed",
            data={
                "post_id": post_id,
                "new_likes_count": new_likes_count,
            },
            room=SioRooms.get_post_room(post_id=post_id),
        )

    async def emit_post_comments_count_changed(
        self, post_id: str, new_comments_count: int
    ):
        await self.emit(
            "post_comments_count_changed",
            data={
                "post_id": post_id,
                "new_comments_count": new_comments_count,
            },
            room=SioRooms.get_post_room(post_id=post_id),
        )
