from aiohttp.web_exceptions import *

from models.role import Role
from config.server_config import SERVER_CONFIG
from utils.sizes import SizeUtils
from packaging.version import Version

class ApiError(Exception):
	def __init__(
			self,
			response_status_code: int = 500,
			server_message: str = 'Unexcepted server error',
			response_message: str = 'Something went wrong',
	):
		super().__init__(server_message)
		self.server_message = server_message
		self.response_status_code = response_status_code
		self.response_message = response_message

	def to_json(self):
		return {
			'error_text': self.response_message
		}

class UnauthorizedError(ApiError):
	def __init__(self, response_message = 'You are not authorized'):
		super().__init__(
			response_status_code = 401,
			server_message = 'Could not found or validate access/refresh token',
			response_message = response_message,
		)

class ForbiddenError(ApiError):
	def __init__(self,
		server_message = 'Forbidden',
		response_message = 'Forbidden'
	):
		super().__init__(403, server_message, response_message)

class ForbiddenForRole(ForbiddenError):
	def __init__(self,
		input_role: Role,
		required_role: Role,
	):
		super().__init__(
			server_message = f'Input role ({input_role.name}), required role: ({required_role.name})',
			response_message = f'Required role: {required_role.name}',
		)

class IncompleteRegistration(ForbiddenError):
	def __init__(self, email):
		super().__init__(
			server_message = f'{email} has not completed registration yet',
			response_message = 'Complete the registration',
		)

class SpamError(ApiError):
	def __init__(self,
		server_message = 'Got spam',
		response_message = 'Too many requests',
	):
		super().__init__(
			response_status_code = 429,
			server_message = server_message,
			response_message = response_message,
		)

class BadRequest(ApiError):
	def __init__(
			self,
			server_message: str,
			response_message: str,
		):
		super().__init__(400, server_message, response_message)

class NotFound(BadRequest):
	def __init__(
			self,
			path: str,
		):
		super().__init__(
			server_message = f'Trying to {path}',
			response_message ='404: Not Found'
		)

class BadDeviceID(BadRequest):
	def __init__(self, valid_error: str = '?'):
		super().__init__(
			server_message = f'Bad device id: {valid_error}',
			response_message = '[device_id] must be specified in request headers',
		)

class BadContentType(BadRequest):
	def __init__(
			self,
			required_type: str,
			input_type: str = '?',
		):
		super().__init__(
			f'Bad content type: {input_type}, required: {required_type}',
			f'Content-Type must be "{required_type}"',
		)

class UnableToDecodeJsonBody(BadRequest):
	def __init__(self, error = '?'):
		super().__init__(error, 'Bad json body')

class ResetContent(ApiError):
	def __init__(
			self,
			server_message: str,
			response_message: str,
		):
		super().__init__(205, server_message, response_message)

class NotModified(ApiError):
	def __init__(
			self,
			server_message: str = 'Not modified',
			response_message: str = 'Nothing to update',
		):
		super().__init__(304, server_message, response_message)

class ValidationError(BadRequest):
	def __init__(self, validate_error_message, server_message = None):
		super().__init__(
			server_message = validate_error_message if server_message is None else server_message,
			response_message = validate_error_message,
		)

class OwnerAlreadyRegistered(ValidationError):
	def __init__(self):
		super().__init__('Owner already registered')

class OwnerNotExist(ValidationError):
	def __init__(self):
		super().__init__('Owner does not exist yet')

class ImageIsTooLarge(BadRequest):
	def __init__(self, request_content_length: str):
		str_size = '?'
		if request_content_length.isdigit():
			str_size = SizeUtils.bytes_to_human_readable(int(request_content_length))
		super().__init__(f'Image is too large ({str_size})', f'Image is too large (max: {SERVER_CONFIG.MAX_IMAGE_SIZE}MB)')

class DatabaseError(ApiError):
	def __init__(
			self,
			server_message: str = 'Unexcepted database error',
		):
		super().__init__(500, 'Database error: ' + server_message)

class CouldNotSendOtpToEmail(BadRequest):
	def __init__(self, email_address, email_error = '?'):
		super().__init__(
			server_message = f"Error on sending OTP code to email {email_address}: {email_error}",
			response_message = f"Could not send the OTP code to the specified email address",
		)

class UserWithEmailHasAlreadyCompletedRegistration(BadRequest):
	def __init__(self, email_address):
		super().__init__(
			server_message = f'User with email ({email_address}) already exists and his registration is completed',
			response_message = 'You are already registered, please log in',
		)

class CouldNotFoundOtpWithEmail(BadRequest):
	def __init__(self, email_address):
		super().__init__(
			server_message = f'Could not found OTP with email: {email_address}',
			response_message = 'Could not found OTP with your email, resend the otp code',
		)

class IncorrectOtpCode(BadRequest):
	def __init__(self):
		super().__init__(
			server_message = 'Incorrect OTP code',
			response_message = 'Incorrect OTP code',
		)

class OtpCodeIsOutdated(BadRequest):
	def __init__(self):
		super().__init__(
			server_message = 'The OTP code is outdated',
			response_message = 'Your OTP code is outdated, resend the new OTP code',
		)

class CouldNotFoundUserWithId(BadRequest):
	def __init__(self, user_id: str):
		super().__init__(
			server_message = f'Could not found user with id ({user_id})',
			response_message = f'Could not found user with id ({user_id})',
		)

class UsernameIsAlreadyTaken(BadRequest):
	def __init__(self, username: str):
		super().__init__(
			server_message = f'Username ({username}) is already taken',
			response_message = f'Username ({username}) is already taken',
		)

class IncorrectLoginData(BadRequest):
	def __init__(self, server_message: str = 'Incorrect login data'):
		super().__init__(
			server_message = server_message,
			response_message = f'Incorrect data',
		)

class CouldNotFoundUserWithSpecifiedData(BadRequest):
	def __init__(self, specified_data):
		super().__init__(
			server_message = f'Could not found user with specified data ({specified_data})',
			response_message = f'Could not found user with specified data ({specified_data})',
		)

class TryingToResetPasswordWithIncompletedRegistration(BadRequest):
	def __init__(self):
		super().__init__(
			server_message = 'Trying to reset password with incompleted registration',
			response_message = "You haven't completed registration",
		)

class AvatarTypeIsNotExternal(BadRequest):
	def __init__(self):
		super().__init__(
			server_message = 'User avatar type is not external',
			response_message = "The target user does not have an external avatar image",
		)

class AlreadyFollowingTargetUser(ResetContent):
	def __init__(self):
		super().__init__(
			server_message = 'Already following the target user',
			response_message = "You are already following the target user",
		)

class IsNotFollowingTargetUser(ResetContent):
	def __init__(self):
		super().__init__(
			server_message = 'Is not following the target user anyway',
			response_message = "You are not following the target user anyway",
		)

class BadImageFileExt(BadRequest):
	def __init__(self, bad_ext):
		super().__init__(
			server_message = f'Got bad image file ext {bad_ext}',
			response_message = f'Bad avatar image file ext, allowed: {SERVER_CONFIG.ALLOWED_IMAGE_EXTENSIONS}',
		)

class CouldNotFoundApkUpdateWithVersion(ValidationError):
	def __init__(self, version: Version):
		super().__init__(f'Could not found apk update with version "{version}"')

class ApkUpdateWithVersionAlreadyExists(ValidationError):
	def __init__(self, version: Version):
		super().__init__(f'Apk update with version ({version}) already exists')