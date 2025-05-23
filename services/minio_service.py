import asyncio
import mimetypes
from enum import Enum
from io import BytesIO

from minio import Minio, S3Error

from config.minio_config import MinioConfig
from models.exceptions.api_exceptions import MinioError, MinioNotFoundError
from models.exceptions.initalize_exceptions import (
    ConfigNotInitalizedButUsingError,
    ServiceNotInitalizedButUsingError,
    UnableToInitializeServiceError,
)


class Buckets(Enum):
    avatars = "avatars"
    posts = "posts"
    messages = "messages"
    apks = "apks"


class MinioService:
    INITALIZED: bool = False
    instance: Minio

    @staticmethod
    async def initialize():
        try:
            if not MinioConfig.INITALIZED:
                raise ConfigNotInitalizedButUsingError(config_name="MinioConfig")
            MinioService.instance = Minio(
                endpoint="minio:9000",
                access_key=MinioConfig.USER,
                secret_key=MinioConfig.PASSWORD,
                secure=False,
            )
            await MinioService._initialize_buckets()
            MinioService.INITALIZED = True
        except Exception as error:
            raise UnableToInitializeServiceError("MinioService") from error

    @staticmethod
    async def _initialize_buckets():
        for bucket in Buckets:
            found = await asyncio.to_thread(
                MinioService.instance.bucket_exists, bucket.value
            )
            if not found:
                await asyncio.to_thread(MinioService.instance.make_bucket, bucket.value)

    @staticmethod
    def guess_mime_type(filename: str) -> str:
        mime, _ = mimetypes.guess_type(filename)
        return mime or "application/octet-stream"

    # @staticmethod
    # async def save_avatar(
    #     avatar_id: str,
    #     original_bytes: BytesIO,
    #     original_filename: str,
    # ):
    #     if not MinioService.INITALIZED:
    #         raise ServiceNotInitalizedButUsingError("MinioService")
    #     try:
    #         original_content_type = MinioService.guess_mime_type(original_filename)
    #         splitted_images = ImageUtils.split(original=original_bytes)
    #         for str_size, buffer in splitted_images.items():
    #             buffer.seek(0)
    #             size = buffer.getbuffer().nbytes
    #             content_type = original_content_type if str_size == 'original' else 'image/jpeg'
    #             await asyncio.to_thread(
    #                 MinioService.instance.put_object,
    #                 bucket_name=Buckets.avatars.value,
    #                 object_name=f"{avatar_id}/{str_size}.jpg",
    #                 data=buffer,
    #                 content_type=content_type,
    #                 length=size,
    #             )

    #         # original_bytes.seek(0)
    #         # content_type = MinioService.guess_mime_type(original_filename)
    #         # size = original_bytes.getbuffer().nbytes
    #         # original_bytes.seek(0)
    #         # await asyncio.to_thread(
    #         #     MinioService.instance.put_object,
    #         #     bucket_name=Buckets.avatars.value,
    #         #     object_name=f"{avatar_id}/{original_filename}",
    #         #     data=original_bytes,
    #         #     length=size,
    #         #     content_type=content_type,
    #         # )
    #         return f"avatar/{avatar_id}"
    #     except S3Error as error:
    #         raise MinioError(error=error) from error

    # @staticmethod
    # async def get_image(bucket: Buckets, key: str):
    #     if not MinioService.INITALIZED:
    #         raise ServiceNotInitalizedButUsingError("MinioService")
    #     try:
    #         data = await asyncio.to_thread(
    #             MinioService.instance.get_object,
    #             bucket_name=bucket.value,
    #             object_name=key,
    #         )
    #         stat = await asyncio.to_thread(
    #             MinioService.instance.stat_object, bucket.value, key
    #         )
    #         return data, stat
    #     except S3Error as error:
    #         if error.code == "NoSuchKey":
    #             raise MinioNotFoundError(key=key)
    #         else:
    #             raise MinioError(error=error) from error

    @staticmethod
    async def save(
        bucket: Buckets, key: str, bytes: BytesIO, filename: str | None = None
    ):
        filename = filename or key
        if not MinioService.INITALIZED:
            raise ServiceNotInitalizedButUsingError("MinioService")
        try:
            bytes.seek(0)
            content_type = MinioService.guess_mime_type(filename)
            size = bytes.getbuffer().nbytes
            bytes.seek(0)
            return await asyncio.to_thread(
                MinioService.instance.put_object,
                bucket_name=bucket.value,
                object_name=key,
                data=bytes,
                length=size,
                content_type=content_type,
            )
        except S3Error as error:
            raise MinioError(error=error) from error

    @staticmethod
    async def get(bucket: Buckets, key: str):
        if not MinioService.INITALIZED:
            raise ServiceNotInitalizedButUsingError("MinioService")
        try:
            data = await asyncio.to_thread(
                MinioService.instance.get_object,
                bucket_name=bucket.value,
                object_name=key,
            )
            stat = await asyncio.to_thread(
                MinioService.instance.stat_object, bucket.value, key
            )
            return data, stat
        except S3Error as error:
            if error.code == "NoSuchKey":
                raise MinioNotFoundError(key=key)
            else:
                raise MinioError(error=error) from error

    @staticmethod
    async def delete(bucket: Buckets, key: str):
        if not MinioService.INITALIZED:
            raise ServiceNotInitalizedButUsingError("MinioService")
        try:
            await asyncio.to_thread(
                MinioService.instance.remove_object,
                bucket_name=bucket.value,
                object_name=key,
            )
        except S3Error as error:
            if error.code == "NoSuchKey":
                raise MinioNotFoundError(key=key)
            else:
                raise MinioError(error=error) from error

