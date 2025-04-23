_base_api_path = '/api/v1'
class PATHS:
	class REGISTRATION:
		_base_path = f'{_base_api_path}/registration'
		CHECK_EMAIL = f'{_base_path}'
		VERIFY_OTP = f'{_base_path}/verify_otp'
		COMPLETE_REGISTRATION = f'{_base_path}/complete'
	class AUTH:
		_base_path = f'{_base_api_path}/auth'
		LOGIN = f'{_base_path}/login'
		LOGOUT = f'{_base_path}/logout'
		REFRESH = f'{_base_path}/refresh'

		class RESET_PASSWORD:
			_base_path = f'{_base_api_path}/auth/reset_password'
			SEND_OTP = f'{_base_path}'
			VERIFY_OTP = f'{_base_path}/verify_otp'
	class USERS:
		_base_path = f'{_base_api_path}/users'
		CHECK_USERNAME = f'{_base_path}/check_username'
		GET_BY_ID = f'{_base_path}/{{user_id}}'
		SEARCH = f'{_base_path}/search'
		UPDATE_PROFILE = f'{_base_path}/update_profile'
		UPDATE_PASSWORD = f'{_base_path}/update_password'
		UPDATE_AVATAR = f'{_base_path}/update_avatar'
		DELETE_AVATAR = f'{_base_path}/delete_avatar'
		GET_AVATAR_IMAGE = f'{_base_path}/avatars/{{user_id}}'
		FOLLOW = f'{_base_path}/follow'
		UNFOLLOW = f'{_base_path}/unfollow'
		GET_FOLLOWINGS = f'{_base_path}/followings'
		GET_FOLLOWERS = f'{_base_path}/followers'
		UPDATE_ROLE = f'{_base_path}/update_role'

	class TEST_USERS:
		_base_path = f'{_base_api_path}/test_users'
		ADMIN_ROLE_TEST = f'{_base_path}/admin_role'
		OWNER_ROLE_TEST = f'{_base_path}/owner_role'

	class APK_UPDATES:
		_base_path = f'{_base_api_path}/apk_updates'
		GET_MANY = f'{_base_path}'
		ADD = f'{_base_path}/add'
		GET_ONE = f'{_base_path}/{{update_id}}'
		DELETE = f'{_base_path}/delete'
		DOWNLOAD = f'{_base_path}/download'

class MIDDLEWARE_PATHS:
	#? Paths that can obly be requested by authorized
	AUTH = (
		PATHS.REGISTRATION.COMPLETE_REGISTRATION,
		PATHS.AUTH.LOGOUT,
		PATHS.USERS._base_path,
		PATHS.TEST_USERS._base_path,
		PATHS.APK_UPDATES.ADD,
		PATHS.APK_UPDATES.DELETE,
	)
	#? Paths where Content-Type must be a json
	JSON_CONTENT_TYPE = (
		PATHS.REGISTRATION._base_path,
		PATHS.AUTH.LOGIN,
		PATHS.AUTH.RESET_PASSWORD.VERIFY_OTP,
		PATHS.USERS.UPDATE_PROFILE,
		PATHS.USERS.UPDATE_PASSWORD,
	)
	#? Paths where Content-Type must be a multipart/form-data
	MULTIPART_FORMDATA_CONTENT_TYPE = (
		PATHS.USERS.UPDATE_AVATAR,
		PATHS.APK_UPDATES.ADD,
	)
	#? Paths where device_id must be specified
	DEVICE_ID_SPECIFIED = (
		PATHS.REGISTRATION.VERIFY_OTP,
		PATHS.AUTH.LOGIN,
		PATHS.AUTH.LOGOUT,
		PATHS.AUTH.REFRESH,
		PATHS.AUTH.RESET_PASSWORD.VERIFY_OTP,
	)
	#? Paths that can only be requested by users after completing thier registration
	IS_REGISTRATION_COMPLETE = PATHS.USERS._base_path,
	OWNER_ROLE = (
		PATHS.TEST_USERS.OWNER_ROLE_TEST,
		PATHS.USERS.UPDATE_ROLE,
		PATHS.APK_UPDATES.ADD,
		PATHS.APK_UPDATES.DELETE,
	)
	ADMIN_ROLE = PATHS.TEST_USERS.ADMIN_ROLE_TEST,


