from logging import Logger
from bcrypt import checkpw
from aiohttp.web import Request, json_response

from services.tokens_service import TokensService
from repositories.user_repository import UserRepositorty
from repositories.otp_repository import OtpRepository
from models.otp import OtpDestiny
from models.exceptions.api_exceptions import *
from utils.my_validators import Validate
from services.email_service import EmailService
from controllers.sio_controller import SioController

class AuthConrtoller:
	def __init__(self, logger: Logger, main_sio_namespace: SioController):
		self._logger = logger
		self._sio = main_sio_namespace

	async def login(self, request: Request):
		body = await request.json()

		username = body.get('username')
		password = body.get('password')

		username_is_valid, valid_error = Validate.username(username)
		if not username_is_valid:
			raise ValidationError(valid_error)

		password_is_valid, valid_error = Validate.password(password)
		if not password_is_valid:
			raise ValidationError(valid_error)

		user = await UserRepositorty.get_by_username(request.db_session, username)
		if user is None:
			raise IncorrectLoginData(server_message=f'Could not found user with username @{username}')

		if not checkpw(password.encode("UTF-8"), user.hashed_password):
			raise IncorrectLoginData(server_message=f'@{username} gave incorrect password')

		access_token, refresh_token = await TokensService.generate_pair_and_save_refresh(
			session = request.db_session,
			user_id = user.id,
			device_id = request.device_id,
			user_role = user.role,
		)

		self._logger.debug(f'@{username} successful logged in!')

		return json_response({
			'access_token': access_token,
			'refresh_token': refresh_token,
			'user': user.to_json(safe = True),
		})

	async def refresh(self, request: Request):
		authorization_headers = request.headers.get('authorization')
		if authorization_headers is None:
			raise UnauthorizedError()
		authorization_list = authorization_headers.split(' ')
		if len(authorization_list) < 2:
			raise UnauthorizedError()
		refresh_token = authorization_list[1]
		try:
			refresh_token_data = TokensService.decode_refresh(refresh_token)
		except:
			raise UnauthorizedError()
		user_id = refresh_token_data.get('id')

		saved_refresh_token = await TokensService.get_refresh_by_user_and_device_ids(
			session = request.db_session,
			user_id = user_id,
			device_id = request.device_id,
		)

		if saved_refresh_token is None or saved_refresh_token.value != refresh_token:
			raise UnauthorizedError()

		user = await UserRepositorty.get_by_id(request.db_session,user_id)

		new_access_token, new_refresh_token = await TokensService.generate_pair_and_save_refresh(
			session = request.db_session,
			user_id = user.id,
			device_id = request.device_id,
			user_role = user.role,
		)

		self._logger.debug(f'@{user.username} generated new token pair')

		return json_response({
			'access_token': new_access_token,
			'refresh_token': new_refresh_token,
			'user': user.to_json(safe = True),
		})

	async def logout(self, request: Request):
		user = await UserRepositorty.get_by_id(request.db_session, request.user_id)
		await self._sio.on_logout(user.current_sid)
		await UserRepositorty.set_current_sid(
			session = request.db_session,
			user_id=user.id,
			new_sid=None,
		)
		await TokensService.delete_refresh(
			session = request.db_session,
			user_id=user.id,
			device_id=request.device_id,
		)
		self._logger.debug(f'@{user.username} has logged out')
		return json_response()

	async def send_otp_to_reset_password(self, request: Request):
		#! Need a type:
		#! e - by email
		#! u - by username

		reset_type = request.query.get('type')
		if not isinstance(reset_type, str) or not reset_type in ('e', 'u',):
			raise ValidationError('[type] must be specified in query ([e] - by email, [u] - by username)')

		user = None
		specified_data = None

		if reset_type == 'e':
			email = request.query.get('email')
			email_is_valid, valid_error = Validate.email(email)
			if not email_is_valid:
				raise ValidationError(valid_error)
			user = await UserRepositorty.get_by_email(request.db_session, email)
			specified_data = email
		else:
			username = request.query.get('username')
			username_is_valid, valid_error = Validate.username(username)
			if not username_is_valid:
				raise ValidationError(valid_error)
			user = await UserRepositorty.get_by_username(request.db_session, username)
			specified_data = username

		if user is None:
			raise CouldNotFoundUserWithSpecifiedData(specified_data)

		if not user.is_registration_completed:
			raise TryingToResetPasswordWithIncompletedRegistration()

		#* Checking for spam to OTP generation
		if not (await OtpRepository.can_update(request.db_session, user.email_address)):
			raise SpamError(
				server_message=f'Got spam ({user.email_address})',
				response_message = 'Wait a minute before resend the OTP code',
			)

		#* Updating user OTP
		otp = await OtpRepository.create_or_update(request.db_session, user.email_address)
		self._logger.info(f'OTP generated: {otp.value}')

		#* Sending OTP to email address
		try:
			await EmailService.send_otp(user.email_address, otp.value, OtpDestiny.reset_password)
		except Exception:
			raise CouldNotSendOtpToEmail(user.email_address)

		return json_response(data = otp.to_json(safe=reset_type == 'e'))

	async def verify_otp_for_reset_password(self, request: Request):
		#! Need a type:
		#! e - by email
		#! u - by username

		reset_type = request.query.get('type')
		if not isinstance(reset_type, str) or not reset_type in ('e', 'u',):
			raise ValidationError('[type] must be specified in query ([e] - by email, [u] - by username)')

		specified_data = None

		if reset_type == 'e':
			email = request.query.get('email')
			email_is_valid, valid_error = Validate.email(email)
			if not email_is_valid:
				raise ValidationError(valid_error)
			user = await UserRepositorty.get_by_email(request.db_session, email)
			specified_data = email
		else:
			username = request.query.get('username')
			username_is_valid, valid_error = Validate.username(username)
			if not username_is_valid:
				raise ValidationError(valid_error)
			user = await UserRepositorty.get_by_username(request.db_session, username)
			specified_data = username

		if user is None:
			raise CouldNotFoundUserWithSpecifiedData(specified_data)

		body = await request.json()
		otp_code = body.get('otp_code')
		otp_code_is_valid, valid_error = Validate.otp_code(otp_code)
		if not otp_code_is_valid:
			raise ValidationError(valid_error)

		await OtpRepository.verify(request.db_session, user.email_address, otp_code)

		self._logger.debug(f'{user.email_address} verified OTP code\n')

		access_token, refresh_token = await TokensService.generate_pair_and_save_refresh(
			session = request.db_session,
			user_id = user.id,
			device_id = request.device_id,
			user_role = user.role,
		)

		return json_response({
			'access_token': access_token,
			'refresh_token': refresh_token,
			'user': user.to_json(safe = True),
		})