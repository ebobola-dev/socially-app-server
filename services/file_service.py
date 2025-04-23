import asyncio
import aiofiles
from io import BytesIO
from pathlib import Path
from packaging.version import Version

class FileService:
	_avatars_dir = 'files/external_avatars'
	_apks_dir = 'files/apks'

	@staticmethod
	async def _check_avatars_dir():
		await asyncio.to_thread(lambda: Path(FileService._avatars_dir).mkdir(parents = True, exist_ok = True))

	@staticmethod
	async def _check_apks_dir():
		await asyncio.to_thread(lambda: Path(FileService._apks_dir).mkdir(parents = True, exist_ok = True))

	@staticmethod
	async def save_avatar(
		user_id: str,
		avatar_bytes: BytesIO,
		avatar_filename_ext: str,
	) -> str:
		await FileService._check_avatars_dir()
		filepath = f'{FileService._avatars_dir}/{user_id}.{avatar_filename_ext}'
		avatar_bytes.seek(0)
		async with aiofiles.open(filepath, 'wb') as avatar_local_file:
			await avatar_local_file.write(await asyncio.to_thread(avatar_bytes.read))
		return filepath

	@staticmethod
	async def delete_avatar(user_id: str):
		directory = Path(FileService._avatars_dir)
		user_avatar_files = await asyncio.to_thread(lambda: list(directory.glob(f"{user_id}.*")))

		for file_path in user_avatar_files:
			if await asyncio.to_thread(file_path.is_file):
				await asyncio.to_thread(file_path.unlink)

	@staticmethod
	async def get_avatar_filepath(user_id: str) -> str | None:
		directory = Path(FileService._avatars_dir)
		matching_user_avatar_image = await asyncio.to_thread(lambda: list(directory.glob(f"{user_id}.*")))
		if matching_user_avatar_image:
			return matching_user_avatar_image[0]
		return None

	@staticmethod
	async def save_apk_update_file(
		apk_file_bytes: BytesIO,
		filename: str,
	):
		await FileService._check_apks_dir()
		filepath = f'{FileService._apks_dir}/{filename}'
		apk_file_bytes.seek(0)
		async with aiofiles.open(filepath, 'wb') as apk_local_file:
			await apk_local_file.write(await asyncio.to_thread(apk_file_bytes.read))
		return filepath

	@staticmethod
	async def delete_apk_update_file(version: Version):
		filepath = Path(f'{FileService._apks_dir}/socially_app-v{version}.apk')
		if await asyncio.to_thread(filepath.is_file):
			await asyncio.to_thread(filepath.unlink)

	@staticmethod
	async def get_apk_filepath(version: Version) -> str | None:
		filepath = Path(f'{FileService._apks_dir}/socially_app-v{version}.apk')
		if await asyncio.to_thread(filepath.is_file):
			return f'{FileService._apks_dir}/socially_app-v{version}.apk'