import asyncio
from logging import Logger

from aiohttp.web import Request, StreamResponse
from aiohttp.web_exceptions import HTTPNotImplemented

from controllers.middlewares import authenticate
from models.exceptions.api_exceptions import ForbiddenError, ValidationError
from models.image_sizes import ImageSizes
from repositories.message_repository import MessagesRepository
from services.minio_service import Buckets, MinioService


class MediaController:
    def __init__(self, logger: Logger):
        self._logger = logger

    @authenticate()
    async def get(self, request: Request):
        category = request.match_info["category"]
        try:
            category = Buckets(category)
        except Exception:
            raise ValidationError(
                field_specific_erros={
                    "category": f"bad value, allowed: {', '.join(tuple(map(lambda b: b.value, Buckets)))}"
                },
                server_message=f"Bad category: {category}",
            )
        key = request.match_info["key"]
        if category.is_image_bucket:
            size = ImageSizes.from_request(request)
            existing_name = await MinioService.find_existing_with_size(
                bucket=category,
                prefix=key,
                requested_size=size,
            )
            data, stat = await MinioService.get_first_with_prefix(
                bucket=category,
                prefix=existing_name,
            )
        else:
            data, stat = await MinioService.get(
                bucket=category,
                key=key,
            )
        stream_response = StreamResponse(
            headers={
                "Content-Type": stat.content_type or "application/octet-stream",
                "Content-Length": str(stat.size),
            }
        )
        await stream_response.prepare(request)
        chunk_size = 8192
        while True:
            chunk = await asyncio.to_thread(data.read, chunk_size)
            if not chunk:
                break
            await stream_response.write(chunk)
        await stream_response.write_eof()
        return stream_response

    @authenticate()
    async def get_avatar_image(self, request: Request):
        avatar_id = request.match_info["avatar_id"]
        size = ImageSizes.from_request(request)

        self._logger.debug(f"{avatar_id=} | {size=}")

        raise HTTPNotImplemented()

    @authenticate()
    async def get_with_folder(self, request: Request):
        category = request.match_info["category"]
        try:
            category = Buckets(category)
        except Exception:
            raise ValidationError(
                {
                    "category": f"bad value, allowed: {', '.join(tuple(map(lambda b: b.value, Buckets)))}"
                }
            )
        folder = request.match_info["folder"]

        # * Check message permission
        if category == Buckets.messages:
            message = await MessagesRepository.get_message_by_id(
                session=request.db_session,
                message_id=folder,
                include_deleted=True,
            )
            if message:
                if request.user_id not in (
                    message.sender_id,
                    message.recipient_id,
                ):
                    raise ForbiddenError(
                        server_message=f"Forbidden for uid:{request.user_id}"
                    )
        # * End check

        key = request.match_info["key"]
        prefix = f"{folder}/{key}"
        if category.is_image_bucket:
            size = ImageSizes.from_request(request)
            existing_name = await MinioService.find_existing_with_size(
                bucket=category,
                prefix=prefix,
                requested_size=size,
            )
            data, stat = await MinioService.get_first_with_prefix(
                bucket=category,
                prefix=existing_name,
            )
        else:
            data, stat = await MinioService.get(
                bucket=category,
                key=f"{folder}/{key}",
            )
        stream_response = StreamResponse(
            headers={"Content-Type": stat.content_type or "application/octet-stream"}
        )
        await stream_response.prepare(request)
        chunk_size = 8192
        while True:
            chunk = await asyncio.to_thread(data.read, chunk_size)
            if not chunk:
                break
            await stream_response.write(chunk)
        await stream_response.write_eof()
        return stream_response
