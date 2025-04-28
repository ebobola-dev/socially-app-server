import asyncio
from logging import Logger
from aiohttp.web import Request, json_response, FileResponse
from packaging.version import Version
from io import BytesIO
from re import fullmatch

from models.exceptions.api_exceptions import *
from controllers.sio_controller import SioController
from repositories.apk_update_repository import ApkUpdateRepository
from models.apk_update import ApkUpdate
from services.file_service import FileService
from config.re_patterns import RE_PATTERNS
from utils.sizes import SizeUtils
from utils.file_utils import FileUtils
from utils.my_validator.my_validator import ValidateField

class ApkUpdatesController:
	def __init__(self, logger: Logger, main_sio_namespace: SioController):
		self._logger = logger
		self._sio = main_sio_namespace

	async def get_one(self, request: Request):
		version = request.match_info.get('update_id')
		ValidateField.version()(version)
		version = Version(version)

		saved_apk_update = await ApkUpdateRepository.get_by_version(
			session = request.db_session,
			version = version,
		)
		if not saved_apk_update:
			raise CouldNotFoundApkUpdateWithVersion(version)
		latest_apk_updates = await ApkUpdateRepository.get(
			session=request.db_session,
			min_version=version,
		)
		if not latest_apk_updates:
			return json_response(data=saved_apk_update.to_json())
		all_descriptions = tuple(map(lambda apk_update: apk_update.description, latest_apk_updates[0:len(latest_apk_updates) - 1]))
		return json_response(data=latest_apk_updates[0].to_json(
			replace_descriptions = all_descriptions,
		))


	async def get_many(self, request: Request):
		min_version = request.query.get('min_version', None)
		if min_version:
			ValidateField.version(field_name='min_version')(min_version)
			min_version = Version(min_version)
		apk_updates = await ApkUpdateRepository.get(
			session = request.db_session,
			min_version = min_version,
		)
		return json_response(
			data = {
				'count': len(apk_updates),
				'apk_updates': tuple(map(lambda apk_update: apk_update.to_json(), apk_updates))
			}
		)

	async def add(self, request: Request):
		reader = await request.multipart()

		apk_file_buffer = None
		version = None
		description = None
		size = 0

		async for part in reader:
			match part.name:
				case 'apk':
					apk_filename = part.filename
					if apk_filename is None or apk_filename == '':
						raise ValidationError({
							'apk': 'must be specified, must be a file'
						})
					match = fullmatch(RE_PATTERNS.APK_UPDATE_FILE, apk_filename)
					if not match:
						raise ValidationError({
							'apk': 'bad filename',
						})
					version = match.group('version')
					apk_file_buffer = BytesIO()
					while chunk := await part.read_chunk(4096):
						size += len(chunk)
						apk_file_buffer.write(chunk)
					apk_file_buffer.seek(0)
				case 'description':
					try:
						description = (await part.text()).strip()
					except:
						raise ValidationError({
							'description': 'must be a string',
						})

		if not apk_file_buffer:
			raise ValidationError({
				'apk': 'must be specified, must be a file',
			})
		if not description:
			raise ValidationError({
				'description': 'must be specified, must be a string',
			})

		ValidateField.version()(version)
		version = Version(version)
		self._logger.debug(f'Got new "{apk_filename}", version: {version}, size: {SizeUtils.bytes_to_human_readable(size)}\n')
		saved_apk_update = await ApkUpdateRepository.get_by_version(
			session = request.db_session,
			version = version,
		)
		if saved_apk_update:
			raise ApkUpdateWithVersionAlreadyExists(version)
		sha256_hash = await asyncio.to_thread(lambda: FileUtils.calculate_sha256_from_bytesio(apk_file_buffer))
		new_apk_update = ApkUpdate(
			version = version,
			description = description,
			file_size = size,
			sha256_hash = sha256_hash,
		)
		new_apk_update = await ApkUpdateRepository.create_new(
			session = request.db_session,
			apk_update = new_apk_update,
		)
		await FileService.save_apk_update_file(
			apk_file_bytes = apk_file_buffer,
			filename = apk_filename,
		)
		#TODO emit users by socket io
		return json_response(
			data = new_apk_update.to_json()
		)

	async def delete(self, request: Request):
		version = request.query.get('version')
		ValidateField.version()(version)
		version = Version(version)
		await FileService.delete_apk_update_file(version=version)
		deleted_count = await ApkUpdateRepository.delete_by_version(
			session = request.db_session,
			version = version
		)
		return json_response({
			'deleted_count': deleted_count,
		})


	async def download(self, request: Request):
		version = request.query.get('version')
		ValidateField.version()(version)
		version = Version(version)
		if not (await ApkUpdateRepository.get_by_version(
			session = request.db_session,
			version = version,
		)):
			raise CouldNotFoundApkUpdateWithVersion(version)
		apk_filepath = await FileService.get_apk_filepath(version)
		return FileResponse(apk_filepath)

