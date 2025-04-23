import asyncio
from uuid import uuid4
from io import BytesIO
from logging import Logger
from aiohttp.web import Request, json_response, FileResponse

from models.gender import Gender
from models.avatar_type import AvatarType
from models.exceptions.api_exceptions import *
from models.pagination import Pagination
from utils.my_validators import Validate
from utils.image_utils import ImageUtils, PillowValidatationResult
from utils.sizes import SizeUtils
from services.file_service import FileService
from controllers.sio_controller import SioController
from repositories.user_repository import UserRepositorty


from config.server_config import SERVER_CONFIG
from config.length_requirements import LENGTH_REQIREMENTS

class UsersController:
	def __init__(self, logger: Logger, main_sio_namespace: SioController):
		self._logger = logger
		self._sio = main_sio_namespace

	async def check_username(self, request: Request):
		username = request.query.get('username')
		username_is_valid, valid_error = Validate.username(username)
		if not username_is_valid:
			raise ValidationError(valid_error)
		user = await UserRepositorty.get_by_username(request.db_session, username)
		self._logger.debug(f'@{username} is {"not exists" if user is None else "exists"}\n')
		return json_response(data = { 'is_exists': user is not None })


	async def get_by_id(self, request: Request):
		user_id = request.match_info['user_id']
		user = await UserRepositorty.get_by_id(request.db_session, user_id)
		if user is None:
			raise CouldNotFoundUserWithId(user_id)
		return json_response(data = user.to_json( safe = user_id == request.user_id ))

	async def search(self, request: Request):
		pagination = Pagination.from_request(request)
		search_data = request.query.get('search_data', '').strip()
		if search_data is None:
			raise ValidationError('Search_data is not specifed')

		if len(search_data) > LENGTH_REQIREMENTS.FULLNAME.MAX:
			raise ValidationError(f'Got bad search_data (not meet the conditions of either the fullname or the username)')

		result = await UserRepositorty.find_by_pattern(
			session=request.db_session,
			pattern=search_data,
			pagination=pagination,
			ignore_id=request.user_id,
		)

		result_json = tuple(map(lambda user: user.to_json(short=True), result))

		return json_response(data = {
			'count': len(result),
			'pagination': {
				'page': pagination.page,
				'per_page': pagination.per_page,
			},
			'users': result_json,
		})

	async def update_profile(self, request: Request):
		user = await UserRepositorty.get_by_id(request.db_session, request.user_id)
		body: dict = await request.json()
		fullname = body.get('fullname')
		username = body.get('username')
		gender = body.get('gender')
		date_of_birth = body.get('date_of_birth')
		about_me = body.get('about_me')
		is_gender_specifed = 'gender' in body.keys()

		#* ---------------- Handle text data ----------------
		#? Logic of processing each field:
		#* 1) Validate if not None (if None - we dont have to change it)
		#* 2) Add to new_data if we have to change it
		new_data = dict()

		if fullname is not None:
			fullname_is_valid, valid_error = Validate.fullname(fullname)
			if not fullname_is_valid:
				raise ValidationError(valid_error)
			if user.fullname != fullname:
				new_data['fullname'] = fullname

		if username is not None:
			username_is_valid, valid_error = Validate.username(username)
			if not username_is_valid:
				raise ValidationError(valid_error)
			if username != user.username:
				user_with_username = await UserRepositorty.get_by_username(request.db_session, username)
				if user_with_username is not None:
					raise UsernameIsAlreadyTaken(username)
				new_data['username'] = username

		if gender is not None:
			gender_is_valid, valid_error = Validate.gender(gender)
			if not gender_is_valid:
				raise ValidationError(valid_error)
			gender = Gender(gender)
			if gender != user.gender:
				new_data['gender'] = Gender(gender)
		elif is_gender_specifed and user.gender is not None:
			new_data['gender'] = None

		if date_of_birth is not None:
			date_of_birth_is_valid, valid_error = Validate.date_of_birth(date_of_birth)
			if not date_of_birth_is_valid:
				raise ValidationError(valid_error)
			if user.date_of_birth != date_of_birth:
				new_data['date_of_birth'] = date_of_birth

		if about_me is not None:
			about_me_is_valid, valid_error = Validate.about_me(about_me)
			if not about_me_is_valid:
				raise ValidationError(valid_error)
			if user.about_me != about_me:
				new_data['about_me'] = about_me

		if not new_data:
			raise NotModified(
				server_message = f'nothing to update, new_data: {new_data}',
			)

		self._logger.debug(f'{user.email_address} will changed: {new_data}')

		updated_user = await UserRepositorty.update_(request.db_session, user.id, new_data)

		return json_response({ "updated_user": updated_user.to_json(safe = True) })

	async def update_password(self, request: Request):
		user = await UserRepositorty.get_by_id(request.db_session, request.user_id)
		body: dict = await request.json()
		new_password = body.get('new_password')
		password_is_valid, valid_error = Validate.password(new_password)
		if not password_is_valid:
			raise ValidationError(valid_error)
		await UserRepositorty.update_password(request.db_session, user.id, new_password)
		self._logger.debug(f'Password updated [{user.email_address}]')
		return json_response()

	async def update_avatar(self, request: Request):
		user = await UserRepositorty.get_by_id(request.db_session, request.user_id)
		content_length = request.headers.get('Content-Length')
		try:
			int_length = int(content_length)
			self._logger.debug(f'(update_avatar) got request {SizeUtils.bytes_to_human_readable(int_length)}')
		except:
			self._logger.debug(f'(update_avatar) got request content_length: {content_length}')

		reader = await request.multipart()

		avatar_file_buffer = None
		file_ext = None
		avatar_type = None

		async for part in reader:
			match part.name:
				case 'avatar':
					avatar_filename = part.filename
					if avatar_filename is None or avatar_filename == '':
						raise ValidationError('Field [avatar] is not a file')
					file_ext = avatar_filename[avatar_filename.rfind('.'):]
					if not file_ext or file_ext == '.' or file_ext[1:] not in SERVER_CONFIG.ALLOWED_IMAGE_EXTENSIONS:
						raise BadImageFileExt(file_ext)
					avatar_file_buffer = BytesIO()
					total_size = 0
					while chunk := await part.read_chunk(4096):
						total_size += len(chunk)
						if total_size > SERVER_CONFIG.MAX_IMAGE_SIZE * 1024 * 1024:
							raise ImageIsTooLarge(content_length)
						avatar_file_buffer.write(chunk)
					avatar_file_buffer.seek(0)
				case 'avatar_type':
					avatar_type = (await part.text()).strip()

		avatar_type_is_valid, valid_error = Validate.avatar_type(avatar_type)
		if not avatar_type_is_valid:
			raise ValidationError(valid_error)

		avatar_type = AvatarType(int(avatar_type))

		if avatar_type == AvatarType.external:
			if not avatar_file_buffer:
				raise ValidationError('Field [avatar] must be specified, if [avatar_type] is external')
			pillow_validation_result = await asyncio.to_thread(ImageUtils.is_valid_by_pillow, avatar_file_buffer)
			is_valid_by_filetype = await asyncio.to_thread(ImageUtils.is_valid_by_filetype, avatar_file_buffer)
			self._logger.debug(f'(update avatar) is valid by filetype: {is_valid_by_filetype}')
			if pillow_validation_result == PillowValidatationResult.unable:
				self._logger.warning('(update avatar) pillow cannot determine the image format')
			else:
				self._logger.debug(f'(update avatar) is valid by pillow: {pillow_validation_result.name}')
			if not (pillow_validation_result != PillowValidatationResult.invalid and is_valid_by_filetype):
				raise ValidationError('Invalid file image, field [avatar]')
			avatar_id = uuid4()
			if user.avatar_id != None:
				await FileService.delete_avatar(user.id)
			await FileService.save_avatar(
				user_id = user.id,
				avatar_bytes = avatar_file_buffer,
				avatar_filename_ext = file_ext[1:],
			)
			updated_user = await UserRepositorty.update_avatar(
				session = request.db_session,
				user_id = user.id,
				new_avatar_type = avatar_type,
				new_avatar_id = avatar_id,
			)
			self._logger.debug(f'(update avatar) @{user.username} uploaded new avatar')
			return json_response(data = { 'updated_user': updated_user.to_json(safe = True) })
		else:
			if user.avatar_type is AvatarType.external:
				await FileService.delete_avatar(user.id)
			updated_user = await UserRepositorty.update_avatar(
				session = request.db_session,
				user_id = user.id,
				new_avatar_type = avatar_type,
			)
			self._logger.debug(f'@{user.username} changed avatar to {avatar_type}')
			return json_response(data = { 'updated_user': updated_user.to_json(safe = True) })

	async def delete_avatar(self, request: Request):
		user_id = request.user_id
		saved_user = await UserRepositorty.get_by_id(request.db_session, user_id)
		if not saved_user:
			raise CouldNotFoundUserWithId(user_id)
		updated_user = await UserRepositorty.delete_avatar(request.db_session, user_id)
		await FileService.delete_avatar(user_id)
		self._logger.debug(f'@{saved_user.username} deleted avatar')
		return json_response(data = { 'updated_user': updated_user.to_json(safe = True) })


	async def get_avatar_image(self, request: Request):
		user_id = request.match_info.get('user_id')
		target_user = await UserRepositorty.get_by_id(request.db_session, user_id)
		if not target_user:
			raise CouldNotFoundUserWithId(user_id)
		if not target_user.avatar_id or target_user.avatar_type != AvatarType.external:
			raise ValidationError('Target user does not have an external avatar')
		avatar_file_path = await FileService.get_avatar_filepath(user_id)
		if avatar_file_path is None:
			self._logger.warning(f'Unable to find avatar file path for @{target_user}, but its exists in database')
			raise ValidationError('Target user does not have an external avatar')
		return FileResponse(avatar_file_path)

	async def follow(self, request: Request):
		user_id = request.user_id
		target_id = request.query.get('target_id')
		if not target_id:
			raise ValidationError('target_id must be specified')
		updated_user = await UserRepositorty.follow(request.db_session, user_id, target_id)

		target_user = await UserRepositorty.get_by_id(request.db_session, target_id)
		if target_user.current_sid:
			await self._sio.emit_new_follower(
				target_sid = target_user.current_sid,
				follower_id = user_id,
				follower_username = updated_user.username,
			)
		return json_response({ "updated_user": updated_user.to_json(safe = True) })


	async def unfollow(self, request: Request):
		user_id = request.user_id
		target_id = request.query.get('target_id')
		if not target_id:
			raise ValidationError('target_id must be specified')
		updated_user = await UserRepositorty.unfollow(request.db_session, user_id, target_id )
		return json_response({ "updated_user": updated_user.to_json(safe = True) })

	async def get_followings(self, request: Request):
		target_id = request.query.get('target_id')
		pagination = Pagination.from_request(request)
		if not target_id:
			raise ValidationError('target_id must be specified')
		target_followings = await UserRepositorty.get_followings(request.db_session, target_id, pagination)
		self._logger.debug(f'(get followings) page: {pagination.page}, limit: {pagination.per_page}, result count: {len(target_followings)}')
		return json_response(data={
			'count': len(target_followings),
			'pagination': {
				'page': pagination.page,
				'per_page': pagination.per_page,
			},
			'followings': list(map(lambda u: u.to_json(short=True), target_followings))
		})

	async def get_followers(self, request: Request):
		target_id = request.query.get('target_id')
		pagination = Pagination.from_request(request)
		if not target_id:
			raise ValidationError('target_id must be specified')
		target_followers = await UserRepositorty.get_followers(request.db_session, target_id, pagination)
		self._logger.debug(f'(get followers) page: {pagination.page}, limit: {pagination.per_page}, result count: {len(target_followers)}')
		return json_response(data={
			'count': len(target_followers),
			'pagination': {
				'page': pagination.page,
				'per_page': pagination.per_page,
			},
			'followers': list(map(lambda u: u.to_json(short=True), target_followers))
		})

	async def update_role(self, request: Request):
		target_id = request.query.get('target_id')
		new_role = request.query.get('new_role')
		#* Validation
		if not target_id:
			raise ValidationError('target_id must be specified')
		role_is_valid, valid_error = Validate.role(new_role)
		if not role_is_valid:
			raise ValidationError(valid_error)
		new_role = Role(int(new_role))
		if new_role == Role.owner:
			raise ValidationError('You can not upgrade role to OWNER using this request')
		target_user = await UserRepositorty.get_by_id(request.db_session, target_id)
		if not target_user:
			raise CouldNotFoundUserWithId(target_id)
		if request.user_id == target_id:
			raise ValidationError('You cannot update the role for youself')
		if not target_user.is_registration_completed:
			raise ValidationError('The target user has not completed registration yet')
		#* End validation
		await UserRepositorty.update_role(
			request.db_session,
			target_id=target_id,
			new_role=new_role,
		)
		owner = await UserRepositorty.get_owner(request.db_session)
		self._logger.warning(f'OWNER({owner.username}) updated role for @{target_user.username} to ({new_role.name})')
		return json_response()