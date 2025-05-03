import asyncio
import shutil
from io import BytesIO
from pathlib import Path

import aiofiles
from packaging.version import Version


class FileService:
    _files_dir = "/files"
    _avatars_dir = f"{_files_dir}/external_avatars"
    _apks_dir = f"{_files_dir}/apks"
    _post_dir = f"{_files_dir}/posts"

    @staticmethod
    async def _check_dir(directory: str):
        await asyncio.to_thread(
            lambda: Path(directory).mkdir(parents=True, exist_ok=True)
        )

    # ******************** Avatars ********************#

    @staticmethod
    async def save_avatar(
        user_id: str,
        avatar_bytes: BytesIO,
        avatar_filename_ext: str,
    ) -> str:
        await FileService._check_dir(FileService._avatars_dir)
        filepath = f"{FileService._avatars_dir}/{user_id}.{avatar_filename_ext}"
        avatar_bytes.seek(0)
        async with aiofiles.open(filepath, "wb") as avatar_local_file:
            await avatar_local_file.write(await asyncio.to_thread(avatar_bytes.read))
        return filepath

    @staticmethod
    async def delete_avatar(user_id: str):
        directory = Path(FileService._avatars_dir)
        user_avatar_files = await asyncio.to_thread(
            lambda: list(directory.glob(f"{user_id}.*"))
        )

        for file_path in user_avatar_files:
            if await asyncio.to_thread(file_path.is_file):
                await asyncio.to_thread(file_path.unlink)

    @staticmethod
    async def get_avatar_filepath(user_id: str) -> str | None:
        directory = Path(FileService._avatars_dir)
        matching_user_avatar_image = await asyncio.to_thread(
            lambda: list(directory.glob(f"{user_id}.*"))
        )
        if matching_user_avatar_image:
            return matching_user_avatar_image[0]
        return None

    # *************************************************#
    # ********************* Apks **********************#

    @staticmethod
    async def save_apk_update_file(
        apk_file_bytes: BytesIO,
        filename: str,
    ):
        await FileService._check_dir(FileService._apks_dir)
        filepath = f"{FileService._apks_dir}/{filename}"
        apk_file_bytes.seek(0)
        async with aiofiles.open(filepath, "wb") as apk_local_file:
            await apk_local_file.write(await asyncio.to_thread(apk_file_bytes.read))
        return filepath

    @staticmethod
    async def delete_apk_update_file(version: Version):
        filepath = Path(f"{FileService._apks_dir}/socially_app-v{version}.apk")
        if await asyncio.to_thread(filepath.is_file):
            await asyncio.to_thread(filepath.unlink)

    @staticmethod
    async def get_apk_filepath(version: Version) -> str | None:
        filepath = Path(f"{FileService._apks_dir}/socially_app-v{version}.apk")
        if await asyncio.to_thread(filepath.is_file):
            return f"{FileService._apks_dir}/socially_app-v{version}.apk"

    # **************************************************#
    # ********************* Posts **********************#

    @staticmethod
    async def save_post_images(post_id: str, images: list[dict], logger = None):
        post_directory = f"{FileService._post_dir}/{post_id}"
        await FileService._check_dir(post_directory)
        logger.debug(f'saving to {post_directory} ({len(images)})')
        async def save_one_post_image(image: dict):
            image_path = f"{post_directory}/{image['index']}{image['ext']}"
            image["content"].seek(0)
            async with aiofiles.open(image_path, "wb") as one_image_file:
                await one_image_file.write(
                    await asyncio.to_thread(image["content"].read)
                )
            return image_path

        return await asyncio.gather(*(save_one_post_image(image) for image in images))

    @staticmethod
    async def delete_all_post_images(post_id: str):
        post_directory = f"{FileService._post_dir}/{post_id}"
        if Path(post_directory).exists() and Path(post_directory).is_dir():
            await asyncio.to_thread(shutil.rmtree, post_directory)

    @staticmethod
    async def get_one_post_image_path(post_id: str, image_index: int, image_ext: str):
        post_directory = f"{FileService._post_dir}/{post_id}"
        return f"{post_directory}/{image_index}{image_ext}"
