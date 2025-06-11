import asyncio
from logging import Logger

import firebase_admin
from firebase_admin import credentials, messaging
from firebase_admin._messaging_utils import UnregisteredError
from firebase_admin.exceptions import FirebaseError, InvalidArgumentError

from database.database import Database
from models.fcm_token import FCMToken
from repositories.fcm_token_repository import FCMTokenRepository
from services.my_logger import MyLogger


class FCMService:
    INITIALIZED: bool = False
    logger: Logger

    @classmethod
    def initialize(cls):
        cred = credentials.Certificate("config/firebase-admin-cred.json")
        firebase_admin.initialize_app(cred)
        cls.logger = MyLogger.get_logger("FCMService")
        cls.INITIALIZED = True

    @classmethod
    async def send_message_to_user(
        cls,
        user_id: str,
        data: dict,
        notification_title: str | None = None,
        notification_body: str | None = None,
        notification_image_url: str | None = None,
    ):
        async with Database.session_maker() as session:
            converted_data = {str(k): str(v) for k, v in data.items()}
            has_notification = bool(
                notification_title or notification_body or notification_image_url
            )
            tokens = await FCMTokenRepository.get_all_by_user(
                session=session,
                user_id=user_id,
            )
            if not tokens:
                cls.logger.debug(
                    f"No tokens by uid '...{user_id[-10:]}', the message has not been sent"
                )
                return

            async def send_and_track(token: FCMToken):
                token_value = token.value
                msg = messaging.Message(
                    token=token_value,
                    data=converted_data,
                    notification=messaging.Notification(
                        title=notification_title,
                        body=notification_body,
                        image=notification_image_url,
                    )
                    if has_notification
                    else None,
                )
                try:
                    await asyncio.to_thread(messaging.send, msg)
                    cls.logger.debug(f"[✓] Sent to: '...{token_value[-10:]}'")
                    return True
                except UnregisteredError:
                    await FCMTokenRepository.delete_by_id(
                        session,
                        token_id=token.id,
                    )
                    cls.logger.error(
                        f"UnregisteredError, token was deleted ('...{token_value[-10:]}')"
                    )
                    return False
                except InvalidArgumentError as e:
                    await FCMTokenRepository.delete_by_id(
                        session,
                        token_id=token.id,
                    )
                    cls.logger.error(
                        f"InvalidArgumentError, token was deleted ('...{token_value[-10:]}'), error: {e}"
                    )
                    return False
                except FirebaseError as e:
                    cls.logger.error(
                        f"Error on sending msg by token: '...{token_value[-10:]}', code: {e.code}, error: {e}"
                    )
                    return False

            send_tasks = [send_and_track(token) for token in tokens]
            results = await asyncio.gather(*send_tasks)
            cls.logger.debug(
                f"Was sent to uid '...{user_id[-10:]}', devices: {results.count(True)}"
            )
