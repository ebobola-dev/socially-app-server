import asyncio
from datetime import datetime
from logging import Logger
from functools import wraps
from socketio import AsyncNamespace
from jwt.exceptions import PyJWTError, ExpiredSignatureError
from database.database import Database

from utils.serialize_util import serialize_value
from models.sio.sio_session import SioSession, AuthorizedSioSession
from models.sio.sio_ack import SioAck
from models.sio.authorize_error import AuthorizeError
from repositories.user_repository import UserRepositorty
from services.tokens_service import TokensService

def check_authorization(handler):
	@wraps(handler)
	async def wrapper(self, sid, *args, **kwargs):
		session = await self.get_session(sid)
		if not isinstance(session, AuthorizedSioSession):
			self._logger.warning(f'[{sid}] Tried to access event without authorization ({handler.__name__})\n')
			return SioAck.failed('You are not authorized').to_json()
		return await handler(self, sid, *args, **kwargs, session = session)
	return wrapper

class SioController(AsyncNamespace):
	def __init__(self, logger: Logger, namespace='/'):
		super().__init__(namespace)
		self._logger = logger
		self._wait_authorization_tasks: dict[str, asyncio.Task] = {}

	async def _wait_authorization(self, sid):
		await asyncio.sleep(60)
		session = await self.get_session(sid)
		if not isinstance(session, AuthorizedSioSession):
			self._logger.info(f"[{sid}] Didn't authorize for a minute, disconnecting...\n")
			await self.disconnect(sid)
			self._cancel_wait_authorization(sid)

	def _cancel_wait_authorization(self, sid):
		task = self._wait_authorization_tasks.get(sid)
		if task:
			task.cancel()
			self._wait_authorization_tasks.pop(sid, None)
			self._logger.debug(f'[{sid}] Wait authorization task canceled\n')

	async def _authorize(self, db_session, sid, data) -> AuthorizedSioSession:
		try:
			device_id = data.get('device_id')
			access_token = data.get('access_token')
			if not device_id:
				raise AuthorizeError(
					internal_message = "Didn't specify device id",
					ack_message = 'Device id is reqiured',
				)
			if access_token is None:
				raise AuthorizeError(
					internal_message = "Access token is not specified",
					ack_message = 'Bad token',
				)
			token_data = TokensService.decode_access(access_token)
			user_id = token_data.get('id')
			user_role = token_data.get('role')
			user = await UserRepositorty.get_by_id(
				session=db_session,
				user_id=user_id,
			)
			if not user:
				raise AuthorizeError(
					internal_message = f"Access token is valid, but unable to find user with id({user_id})",
					ack_message = 'Bad token',
				)
			refresh_token_model = await TokensService.get_refresh_by_user_and_device_ids(
				session=db_session,
				user_id=user_id,
				device_id=device_id,
			)
			if not refresh_token_model:
				raise AuthorizeError(
					internal_message = f"Access token is valid and user found, but unable to find refresh token in database with device_id({device_id}) and user_id({user_id})",
					ack_message = 'Bad token',
				)
			return AuthorizedSioSession(
				sid = sid,
				user_id = user_id,
				user_role = user_role,
				device_id=device_id,
			)
		except ExpiredSignatureError:
			raise AuthorizeError(
				internal_message = f"Access token has expired",
				ack_message = 'Token has expired',
			)
		except PyJWTError as decoding_error:
			raise AuthorizeError(
				internal_message = f"Unable to decode access token: {decoding_error}",
				ack_message = 'Bad token',
			)
		except Exception as unexcepted_error:
			raise AuthorizeError(
				internal_message = f"Unecxecpted error on authorization: {unexcepted_error}"
			)

	#* ------------------------ Event Listeners ------------------------
	async def on_connect(self, sid, environ, auth = None):
		await self.save_session(sid, SioSession(sid))
		self._wait_authorization_tasks[sid] = asyncio.create_task(self._wait_authorization(sid))
		self._logger.info(f'[{sid}] Connected, waiting for authorization...\n')

	async def on_disconnect(self, sid, reason):
		async with Database.session_maker() as db_session:
			self._logger.info(f'[{sid}] Disconnected ({reason})\n')
			self._cancel_wait_authorization(sid)
			session: SioSession = await self.get_session(sid)

			#* Set user disconnected
			if isinstance(session, AuthorizedSioSession):
				try:
					updated_user = await UserRepositorty.set_current_sid(db_session, session.user_id, new_sid = None)
					await db_session.commit()
					await self.emit_user_is_offline(
						user_id = session.user_id,
						last_seen = updated_user.last_seen,
					)
				except Exception as db_error:
					await db_session.rollback()
					self._logger.error(f'(on_disconnect) Error on set current sid to user {session.user_id}: {db_error}')

	async def on_authorize(self, sid, data = None):
		if not data or not isinstance(data, dict):
			return SioAck.failed('Bad authorization data').to_json()
		async with Database.session_maker() as db_session:
			try:
				authorized_session = await self._authorize(
					db_session = db_session,
					sid = sid,
					data = data,
				)
				await self.save_session(sid, authorized_session)
				await UserRepositorty.set_current_sid(
					session = db_session,
					user_id = authorized_session.user_id,
					new_sid = sid,
				)
				await db_session.commit()
				self._logger.info(f'[{sid}] Successfuly authorized\n')
				self._cancel_wait_authorization(sid)
				return SioAck.success().to_json()
			except AuthorizeError as authorized_error:
				self._logger.error(f"[{sid}] Couldn't authorize: {authorized_error.internal_message}\n")
				return SioAck.failed(authorized_error.ack_message).to_json()
			except Exception as error:
				await db_session.rollback()
				self._logger.error(f"[{sid}] unexcepted error on authorize: {error}\n")
				return SioAck.failed('Something went wrong').to_json()


	@check_authorization
	async def on_put_app_in_background(self, sid, data = None, session: AuthorizedSioSession = None):
		self._logger.debug(f'[{sid}] Set user offline\n')

		#* Set user offline
		async with Database.session_maker() as db_session:
			try:
				updated_user = await UserRepositorty.toggle_online(db_session, session.user_id, False)
				await db_session.commit()
				await self.emit_user_is_offline(
					user_id = session.user_id,
					last_seen = updated_user.last_seen
				)
				return SioAck.success().to_json()
			except Exception as error:
				self._logger.error(f'(on_put_app_in_background) error on toggle online: {error}')
				await db_session.rollback()
				return SioAck.failed()

	@check_authorization
	async def on_put_app_in_foreground(self, sid, data = None, session: AuthorizedSioSession = None):
		self._logger.debug(f'[{sid}] Set user online\n')
		await self.emit_user_is_online(session.user_id)

		#* Set user online
		async with Database.session_maker() as db_session:
			try:
				await UserRepositorty.toggle_online(db_session, session.user_id, True)
				await db_session.commit()
				return SioAck.success().to_json()
			except Exception as error:
				self._logger.error(f'(on_put_app_in_background) error on toggle online: {error}')
				await db_session.rollback()
				return SioAck.failed()

	#* ------------------------ Emitters ------------------------
	async def on_logout(self, user_sid: str):
		if user_sid:
			await self.disconnect(user_sid)

	async def emit_user_is_offline(self, user_id: str, last_seen: datetime):
		await self.emit('user_is_offline',  {'user_id': user_id, 'last_seen': serialize_value(last_seen)})

	async def emit_user_is_online(self, user_id: str):
		await self.emit('user_is_online',  {'user_id': user_id})

	async def emit_new_follower(
		self,
		target_sid: str,
		follower_id: str,
		follower_username: str,
	):
		await self.emit(
			event = 'new_follower',
			data = {
				'follower_id': follower_id,
				'follower_username': follower_username
			},
			to = target_sid,
		)