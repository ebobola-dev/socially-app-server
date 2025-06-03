import asyncio
from io import BytesIO
from logging import Logger

from aiohttp.web import Request, json_response

from config.length_requirements import LengthRequirements
from config.server_config import ServerConfig
from controllers.middlewares import authenticate, content_type_is_multipart
from controllers.sio_controller import SioController
from models.exceptions.api_exceptions import (
    BadImageFileExtError,
    ForbiddenToAttachMessageError,
    ForbiddenToDeleteMessageError,
    ForbiddenToReadMessageError,
    ImageIsTooLargeError,
    InvalidImageError,
    MessageIdNotSpecifiedError,
    MessageNotFoundError,
    PostNotFoundError,
    TooManyImagesInMessageError,
    UserIdNotSpecifiedError,
    UserNotFoundError,
    ValidationError,
)
from models.message import Message
from models.pagination import Pagination
from repositories.message_repository import MessagesRepository
from repositories.post_repository import PostRepository
from repositories.user_repository import UserRepository
from services.minio_service import Buckets, MinioService
from utils.image_utils import ImageUtils, PillowValidatationResult


class MessagesController:
    def __init__(self, logger: Logger, main_sio_namespace: SioController):
        self._logger = logger
        self._sio = main_sio_namespace

    @authenticate()
    async def get_chats(self, request: Request):
        pagination = Pagination.from_request(request)
        user_id = request.user_id

        chats = await MessagesRepository.get_chats_by_user_id(
            session=request.db_session,
            user_id=user_id,
            pagination=pagination,
        )
        json_chats = tuple(
            map(
                lambda chat: chat.to_json(detect_rels_for_user_id=request.user_id),
                chats,
            )
        )

        return json_response(
            {
                "count": len(json_chats),
                "chats": json_chats,
                "pagination": {
                    "offset": pagination.offset,
                    "limit": pagination.limit,
                },
            }
        )

    @authenticate()
    async def get_messages(self, request: Request):
        pagination = Pagination.from_request(request)
        target_user_id = request.query.get("target_uid")
        if not target_user_id:
            raise UserIdNotSpecifiedError(field_name="target_uid")
        target_user = await UserRepository.get_by_id(
            session=request.db_session,
            user_id=target_user_id,
            include_deleted=True,
        )
        if not target_user:
            raise UserNotFoundError(
                user_id=target_user_id, error_message="Target user not found"
            )
        messages = await MessagesRepository.get_messages(
            session=request.db_session,
            current_user_id=request.user_id,
            other_user_id=target_user_id,
            pagination=pagination,
        )
        json_messages = tuple(
            map(
                lambda msg: msg.to_json(
                    detect_rels_for_user_id=request.user_id,
                ),
                messages,
            )
        )

        return json_response(
            {
                "count": len(json_messages),
                "messages": json_messages,
                "pagination": {
                    "offset": pagination.offset,
                    "limit": pagination.limit,
                },
            }
        )

    @authenticate()
    @content_type_is_multipart()
    async def create_message(self, request: Request):
        target_uid = request.query.get("target_uid")
        if not target_uid:
            raise UserIdNotSpecifiedError(field_name="target_uid")
        target_user = await UserRepository.get_by_id(
            session=request.db_session,
            user_id=target_uid,
        )
        if not target_user:
            raise UserNotFoundError(target_uid)

        # ************************** Reading the input data **************************#
        reader = await request.multipart()
        text_content: str = ""
        images: list[dict] = []
        attached_message_id: str | None = None
        attached_post_id: str | None = None

        async for part in reader:
            match part.name:
                case "text":
                    if part.filename:
                        raise ValidationError({"text": "must be a string field"})
                    try:
                        text_content = (await part.text()).strip()
                    except Exception:
                        raise ValidationError({"text": "must be a string field"})
                    if len(text_content) > LengthRequirements.MessageTextContent.MAX:
                        raise ValidationError({"text": "too long, max: 10000 characters"})
                case "attached_message_id":
                    if part.filename:
                        raise ValidationError(
                            {"attached_message_id": "must be a string field"}
                        )
                    try:
                        attached_message_id = (await part.text()).strip()
                    except Exception:
                        raise ValidationError(
                            {"attached_message_id": "must be a string field"}
                        )
                case "attached_post_id":
                    if part.filename:
                        raise ValidationError(
                            {"attached_post_id": "must be a string field"}
                        )
                    try:
                        attached_post_id = (await part.text()).strip()
                    except Exception:
                        raise ValidationError(
                            {"attached_post_id": "must be a string field"}
                        )
                case "images":
                    current_index = len(images)
                    if current_index == ServerConfig.MAX_IMAGES_IN_MESSAGE:
                        raise TooManyImagesInMessageError()
                    filename = part.filename
                    if not filename:
                        raise ValidationError(
                            {"images": "must be an array of files(images)"}
                        )
                    file_ext = filename[filename.rfind(".") :]
                    if (
                        not file_ext
                        or file_ext == "."
                        or file_ext[1:] not in ServerConfig.ALLOWED_IMAGE_EXTENSIONS
                    ):
                        raise BadImageFileExtError(file_ext)
                    image_file_buffer = BytesIO()
                    total_size = 0
                    while chunk := await part.read_chunk(4096):
                        total_size += len(chunk)
                        if total_size > ServerConfig.MAX_IMAGE_SIZE * 1024 * 1024:
                            raise ImageIsTooLargeError(
                                filename=filename,
                            )
                        image_file_buffer.write(chunk)
                    image_file_buffer.seek(0)
                    pillow_validation_result = await asyncio.to_thread(
                        ImageUtils.is_valid_by_pillow, image_file_buffer
                    )
                    is_valid_by_filetype = await asyncio.to_thread(
                        ImageUtils.is_valid_by_filetype, image_file_buffer
                    )
                    if (
                        not is_valid_by_filetype
                        or pillow_validation_result == PillowValidatationResult.invalid
                    ):
                        raise InvalidImageError(field_name="image", filename=filename)
                    images.append(
                        {
                            "index": current_index,
                            "ext": file_ext,
                            "content": image_file_buffer,
                            "size": total_size,
                            "file_key": f"{current_index}{file_ext}",
                        }
                    )

        # ************************ End reading the input data ************************#
        # *********************** Check attached records exist ***********************#

        if attached_post_id:
            attached_post = await PostRepository.get_by_id_with_relations(
                session=request.db_session, post_id=attached_post_id
            )
            if not attached_post:
                raise PostNotFoundError(
                    post_id=attached_post_id,
                    error_message="Attached post not found",
                )
        attached_message = None
        if attached_message_id:
            attached_message = await MessagesRepository.get_message_by_id(
                session=request.db_session,
                message_id=attached_message_id,
            )
            if not attached_message:
                raise MessageNotFoundError(
                    message_id=attached_message_id,
                    error_message="Attached message not found",
                )
            if request.user_id not in (
                attached_message.sender_id,
                attached_message.recipient_id,
            ):
                raise ForbiddenToAttachMessageError()

        # ********************* End check attached records exist *********************#

        attached_image_keys: list[str] = (
            list(map(lambda img_data: img_data["file_key"], images)) if images else None
        )

        # ************************** Attachment validation ************************** #

        attachment_type = Message.validate_attachments(
            text_content=text_content,
            attached_image_keys=attached_image_keys,
            attached_message_id=attached_message_id,
            attached_post_id=attached_post_id,
        )

        # ************************ End attachment validation ************************ #
        # ******************************* Devil logic ******************************* #

        new_messages: list[Message] = []
        if attached_message:
            if text_content:
                # % First message - only additional text
                first_message = await MessagesRepository.create_message(
                    session=request.db_session,
                    message=Message.new(
                        sender_id=request.user_id,
                        recipient_id=target_uid,
                        text_content=text_content,
                    ),
                )
                new_messages.append(first_message)

            # % Cloned message
            cloned_message = await MessagesRepository.create_message(
                session=request.db_session,
                message=attached_message.copy_for_forwarding(
                    sender_id=request.user_id,
                    recipient_id=target_uid,
                ),
            )
            new_messages.append(cloned_message)

            # % Copying attached message images if they exist
            if attached_message.attached_image_keys:
                for image_key in attached_message.attached_image_keys:
                    await MinioService.copy(
                        source_bucket=Buckets.messages,
                        source_key=f"{attached_message.id}/{image_key}",
                        new_key=f"{cloned_message.id}/{image_key}",
                    )
        else:
            # % Usual message, without forwarding
            new_message = await MessagesRepository.create_message(
                session=request.db_session,
                message=Message.new(
                    sender_id=request.user_id,
                    recipient_id=target_uid,
                    text_content=text_content,
                    attachment_type=attachment_type,
                    attached_image_keys=attached_image_keys,
                    attached_post_id=attached_post_id,
                ),
            )
            new_messages.append(new_message)

            # % Saving attached images
            for image in images:
                await MinioService.save(
                    bucket=Buckets.messages,
                    key=f"{new_message.id}/{image['file_key']}",
                    bytes=image["content"],
                )

        # ***************************** End devil logic ***************************** #

        for new_msg in new_messages:
            self._logger.debug(
                f"New message({new_msg.id}) created: @{new_msg.sender.username} -> @{new_msg.recipient.username}"
            )
            self._logger.debug(f"Text content: {new_msg.text_content}")
            self._logger.debug(f"Attachemnt type: {new_msg.attachment_type}")
            self._logger.debug(f"Attached post id: {new_msg.attached_post_id}")
            self._logger.debug(f"Attached images: {new_msg.attached_image_keys}")
            if new_msg.forwarded_from_user_id:
                self._logger.debug(
                    f"Forwarded from user: @{new_msg.forwarded_from_user.username}"
                )
            self._logger.debug("")
        json_messages_for_sender = tuple(
            map(
                lambda new_msg: new_msg.to_json(
                    detect_rels_for_user_id=request.user_id,
                ),
                new_messages,
            )
        )
        json_messages_for_target = tuple(
            map(
                lambda new_msg: new_msg.to_json(
                    detect_rels_for_user_id=target_uid,
                ),
                new_messages,
            )
        )
        await self._sio.emit_user(
            user_id=request.user_id,
            event="new_messages",
            data={
                "new_messages": json_messages_for_sender,
                "chat_opponent_id": target_uid,
            },
        )
        await self._sio.emit_user(
            user_id=target_uid,
            event="new_messages",
            data={
                "new_messages": json_messages_for_target,
                "chat_opponent_id": request.user_id,
            },
        )
        return json_response({"new_messages": json_messages_for_sender})

    @authenticate()
    async def delete_message(self, request: Request):
        message_id = request.query.get("message_id")
        if not message_id:
            raise MessageIdNotSpecifiedError()
        target_message = await MessagesRepository.get_message_by_id(
            session=request.db_session,
            message_id=message_id,
        )
        if not target_message:
            raise MessageNotFoundError(message_id)
        if target_message.sender_id != request.user_id:
            raise ForbiddenToDeleteMessageError()

        image_keys = (
            target_message.attached_image_keys.copy()
            if target_message.attached_image_keys
            else []
        )
        (
            deleted_message,
            previous_message,
        ) = await MessagesRepository.soft_delete_message(
            session=request.db_session,
            target_message_id=message_id,
        )
        for image_key in image_keys:
            await MinioService.delete(
                bucket=Buckets.messages,
                key=f"{message_id}/{image_key}",
            )

        json_deleted_message = deleted_message.to_json(
            detect_rels_for_user_id=request.user_id,
        )

        json_chat_last_message_for_sender = None
        json_chat_last_message_for_recipient = None
        if previous_message:
            json_chat_last_message_for_sender = previous_message.to_json(
                short=True,
                detect_rels_for_user_id=deleted_message.sender_id,
            )
            json_chat_last_message_for_recipient = previous_message.to_json(
                short=True,
                detect_rels_for_user_id=deleted_message.recipient_id,
            )

        await self._sio.emit_user(
            user_id=deleted_message.sender_id,
            event="message_was_deleted",
            data={
                "message_id": deleted_message.id,
                "chat_opponent_id": deleted_message.recipient_id,
                "previous_message": json_chat_last_message_for_sender,
            },
        )
        await self._sio.emit_user(
            user_id=deleted_message.recipient_id,
            event="message_was_deleted",
            data={
                "message_id": deleted_message.id,
                "chat_opponent_id": deleted_message.sender_id,
                "previous_message": json_chat_last_message_for_recipient,
            },
        )
        return json_response(
            {
                "deleted_message": json_deleted_message,
                "previous_message": json_chat_last_message_for_sender,
            }
        )

    @authenticate()
    async def mark_readed(self, request: Request):
        message_id = request.query.get("message_id")
        if not message_id:
            raise MessageIdNotSpecifiedError()
        target_message = await MessagesRepository.get_message_by_id(
            session=request.db_session,
            message_id=message_id,
        )
        if not target_message:
            raise MessageNotFoundError(message_id)
        if target_message.recipient_id != request.user_id:
            raise ForbiddenToReadMessageError()
        if target_message.readed:
            return json_response(
                target_message.to_json(detect_rels_for_user_id=request.user_id)
            )

        updated_message = await MessagesRepository.mark_readed(
            session=request.db_session,
            message_id=message_id,
        )
        await self._sio.emit_user(
            user_id=updated_message.sender_id,
            event="message_was_read",
            data={
                "message_id": updated_message.id,
                "chat_opponent_id": updated_message.recipient_id,
            },
        )
        return json_response(
            updated_message.to_json(detect_rels_for_user_id=request.user_id)
        )
