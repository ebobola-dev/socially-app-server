import asyncio
import mimetypes
from datetime import timedelta
from enum import Enum
from io import BytesIO

from minio import Minio, S3Error
from minio.commonconfig import CopySource

from config.minio_config import MinioConfig
from models.exceptions.api_exceptions import MinioError, MinioNotFoundError
from models.exceptions.initalize_exceptions import (
    ConfigNotInitalizedButUsingError,
    ServiceNotInitalizedButUsingError,
    UnableToInitializeServiceError,
)
from models.image_sizes import ImageSizes


class Buckets(Enum):
    avatars = "avatars"
    posts = "posts"
    messages = "messages"
    apks = "apks"

    @property
    def is_image_bucket(self):
        return self != Buckets.apks


class BucketStat:
    def __init__(self, bucket: Buckets, total_objects: int, total_size: int):
        self.bucket = bucket
        self.total_objects = total_objects
        self.total_size = total_size

    def to_json(self):
        return {
            "bucket": self.bucket.value,
            "total_objects": self.total_objects,
            "total_size": self.total_size,
        }


class MinioStat:
    def __init__(
        self,
        avatars_stat: BucketStat,
        posts_stat: BucketStat,
        messages_stat: BucketStat,
        apks: BucketStat,
    ):
        self.avatars_stat = avatars_stat
        self.posts_stat = posts_stat
        self.messages_stat = messages_stat
        self.apks = apks

    def to_json(self):
        return {
            "avatars_stat": self.avatars_stat.to_json(),
            "posts_stat": self.posts_stat.to_json(),
            "messages_stat": self.messages_stat.to_json(),
            "apks": self.apks.to_json(),
        }


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
    async def get_first_with_prefix(bucket: Buckets, prefix: str):
        if not MinioService.INITALIZED:
            raise ServiceNotInitalizedButUsingError("MinioService")
        try:
            objects = tuple(
                await asyncio.to_thread(
                    MinioService.instance.list_objects,
                    bucket_name=bucket.value,
                    prefix=prefix,
                    recursive=True,
                )
            )
            if not objects:
                raise MinioNotFoundError(key=f"prefix: {prefix}")
            key = objects[0].object_name
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
                raise MinioNotFoundError(key=f"prefix: {prefix}")
            else:
                raise MinioError(error=error) from error

    @staticmethod
    async def copy(
        source_bucket: Buckets,
        source_key: str,
        to_bucket: Buckets | None = None,
        new_key: str | None = None,
    ):
        if not MinioService.INITALIZED:
            raise ServiceNotInitalizedButUsingError("MinioService")
        to_bucket = to_bucket or source_bucket
        new_key = new_key or source_key
        try:
            await asyncio.to_thread(
                MinioService.instance.copy_object,
                bucket_name=to_bucket.value,
                object_name=new_key,
                source=CopySource(
                    bucket_name=source_bucket.value,
                    object_name=source_key,
                ),
            )
        except S3Error as error:
            if error.code == "NoSuchKey":
                raise MinioNotFoundError(key=source_key)
            else:
                raise MinioError(error=error) from error

    @staticmethod
    async def copy_message_images(
        source_msg_id: str,
        to_msg_id: str,
    ):
        if not MinioService.INITALIZED:
            raise ServiceNotInitalizedButUsingError("MinioService")
        try:
            objects = tuple(
                await asyncio.to_thread(
                    MinioService.instance.list_objects,
                    bucket_name=Buckets.messages.value,
                    prefix=source_msg_id,
                    recursive=True,
                )
            )
            if not objects:
                raise MinioNotFoundError(key=f"messages by prefix: {source_msg_id}")
            for obj in objects:
                source_object_name = obj.object_name
                new_object_name = source_object_name.replace(
                    source_msg_id,
                    to_msg_id,
                )
                await asyncio.to_thread(
                    MinioService.instance.copy_object,
                    bucket_name=Buckets.messages.value,
                    object_name=new_object_name,
                    source=CopySource(
                        bucket_name=Buckets.messages.value,
                        object_name=source_object_name,
                    ),
                )
        except S3Error as error:
            if error.code == "NoSuchKey":
                raise MinioNotFoundError(key=f"messages by prefix: {source_msg_id}")
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

    @staticmethod
    async def delete_all_by_prefix(bucket: Buckets, prefix: str):
        if not MinioService.INITALIZED:
            raise ServiceNotInitalizedButUsingError("MinioService")
        try:
            objects = tuple(
                await asyncio.to_thread(
                    MinioService.instance.list_objects,
                    bucket_name=bucket.value,
                    prefix=prefix,
                    recursive=True,
                )
            )
            if not objects:
                raise MinioNotFoundError(key=f"prefix: {prefix}")
            for obj in objects:
                await asyncio.to_thread(
                    MinioService.instance.remove_object,
                    bucket_name=bucket.value,
                    object_name=obj.object_name,
                )
        except S3Error as error:
            if error.code == "NoSuchKey":
                raise MinioNotFoundError(key=f"prefix: {prefix}")
            else:
                raise MinioError(error=error) from error

    @staticmethod
    def get_bucket_stats_sync(bucket: Buckets) -> BucketStat:
        total_size = 0
        total_objects = 0
        for obj in MinioService.instance.list_objects(bucket.value, recursive=True):
            total_size += obj.size
            total_objects += 1
        return BucketStat(
            bucket=bucket,
            total_objects=total_objects,
            total_size=total_size,
        )

    @staticmethod
    async def get_all_stats() -> set[BucketStat]:
        stats = await asyncio.gather(
            *(
                asyncio.to_thread(
                    MinioService.get_bucket_stats_sync,
                    bucket,
                )
                for bucket in Buckets
            )
        )
        return set(stats)

    @staticmethod
    async def find_existing_with_size(
        bucket: Buckets,
        prefix: str,
        requested_size: ImageSizes,
    ) -> str:
        for size in ImageSizes.get_next_available_size(requested_size):
            try:
                objects = tuple(
                    await asyncio.to_thread(
                        MinioService.instance.list_objects,
                        bucket_name=bucket.value,
                        prefix=f"{prefix}/{size.str_view}",
                    )
                )
                if objects:
                    return objects[0].object_name
            except S3Error as e:
                if e.code != "NoSuchKey":
                    raise MinioError(error=e) from e
        raise MinioNotFoundError(key=f"{prefix=}, {requested_size=}")

    @staticmethod
    async def generate_temp_link(
        bucket: Buckets, key: str, expires=timedelta(minutes=5)
    ) -> str:
        if not MinioService.INITALIZED:
            raise ServiceNotInitalizedButUsingError("MinioService")
        try:
            return await asyncio.to_thread(
                MinioService.instance.presigned_get_object,
                bucket_name=bucket.value,
                object_name=key,
                expires=expires,
            )
        except S3Error as error:
            if error.code == "NoSuchKey":
                raise MinioNotFoundError(key=key)
            else:
                raise MinioError(error=error) from error
