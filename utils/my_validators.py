from datetime import date
from re import fullmatch
from packaging.version import Version

from models.otp import Otp
from models.gender import Gender
from models.avatar_type import AvatarType
from models.role import Role
from config.length_requirements import LENGTH_REQIREMENTS
from config.re_patterns import RE_PATTERNS
from utils.datetime_utls import DateTimeUtils

class Validate:
	def email(email):
		if email is None:
			return False, 'Email is not specified'
		if not fullmatch(RE_PATTERNS.EMAIL, email):
			return False, 'Invalid email'
		return True, None

	def otp_code(otp_code):
		if otp_code is None:
			return False, 'OTP code not specified'
		if not Otp.is_valid_value(otp_code):
			return False, 'Invalid OTP'
		return True, None

	def fullname(fullname):
		if not isinstance(fullname, str | None):
			return False, 'The fullname must be a string type or nullable'
		if isinstance(fullname, str) and len(fullname) > LENGTH_REQIREMENTS.FULLNAME.MAX:
			return False, f'The fullname must not contain more than {LENGTH_REQIREMENTS.FULLNAME.MAX} characters'
		return True, None

	def date_of_birth(date_of_birth):
		if not isinstance(date_of_birth, str):
			return False, 'Date of birth must be specified, must be a string type, the date in iso format'
		if not DateTimeUtils.is_valid_iso_string_date(date_of_birth):
			return False, 'Date of birth must be specified, must be a string type, the date in iso format'

		date_of_birth = date.fromisoformat(date_of_birth)
		different_time = date.today() - date_of_birth

		if different_time.days <= 0:
			return False, 'Date of birth must be a date before today'
		return True, None

	def gender(gender):
		if not isinstance(gender, int | None):
			return False, 'Gender must be a int type or nullable (1 - male, 2 - female)'
		if isinstance(gender, int) and not 1 <= gender <= len(Gender):
			return False, 'Gender must be a number from 1 to 2 (1 - male, 2 - female)'
		return True, None

	def about_me(about_me):
		if not isinstance(about_me, str | None):
			return False, '"about me" must be a string type or nullable'
		if isinstance(about_me, str) and len(about_me) > LENGTH_REQIREMENTS.ABOUT_ME.MAX:
			return False, f'"about me" must not contain more than {LENGTH_REQIREMENTS.ABOUT_ME.MAX} characters'
		return True, None

	def username(username):
		if username is None:
			return False, f'username must be specified ({LENGTH_REQIREMENTS.USERNAME.TEXT})'
		if not isinstance(username, str):
			return False, f'username must be a string type ({LENGTH_REQIREMENTS.USERNAME.TEXT})'
		if not fullmatch(RE_PATTERNS.USERNAME, username):
			return False, f'username - {LENGTH_REQIREMENTS.USERNAME.TEXT}'
		return True, None

	def password(password):
		if password is None:
			return False, f'password must be specified ({LENGTH_REQIREMENTS.PASSWORD.TEXT})'
		if not isinstance(password, str):
			return False, f'password must be a string type ({LENGTH_REQIREMENTS.PASSWORD.TEXT})'
		if not fullmatch(RE_PATTERNS.PASSWORD, password):
			return False, f'password - {LENGTH_REQIREMENTS.PASSWORD.TEXT}'
		return True, None

	def device_id(device_id):
		if device_id is None:
			return False, f'device id must be specified'
		if not isinstance(device_id, str):
			return False, 'device id must be a string type'
		if not len(device_id):
			return False, 'device id is empty'
		return True, None

	def avatar_type(avatar_type):
		if not isinstance(avatar_type, int | str):
			return False, 'avatar_type must be specififed, integer or string (0-10)'
		if isinstance(avatar_type, int) and not avatar_type in range(len(AvatarType)):
			return False, 'avatar_type must be 0 - 10'
		if isinstance(avatar_type, str):
			if not avatar_type.isdigit():
				return False, 'avatar_type must be 0 - 10'
			if int(avatar_type) not in range(len(AvatarType)):
				return False, 'avatar_type must be 0 - 10'
		return True, None

	def role(role):
		if not isinstance(role, int | str):
			return False, 'role must be specififed, integer or string (1-3)'
		if isinstance(role, int) and not role in range(1, len(Role) + 1):
			return False, f'role must be 1 - {len(Role)}'
		if isinstance(role, str):
			if not role.isdigit():
				return False, f'role must be 1 - {len(Role)}'
			if int(role) not in range(1, len(Role) + 1):
				return False, f'role must be 1 - {len(Role)}'
		return True, None

	def version(version):
		try:
			Version(version)
			return True, None
		except:
			return False, 'Invalid version'