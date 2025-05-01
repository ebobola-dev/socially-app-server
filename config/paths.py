_base_api_path = "/api/v1"


class Paths:
    class Registration:
        _base_path = f"{_base_api_path}/registration"
        CHECK_EMAIL = f"{_base_path}"
        VERIFY_OTP = f"{_base_path}/verify_otp"
        COMPLETE_REGISTRATION = f"{_base_path}/complete"

    class Auth:
        _base_path = f"{_base_api_path}/auth"
        LOGIN = f"{_base_path}/login"
        LOGOUT = f"{_base_path}/logout"
        REFRESH = f"{_base_path}/refresh"

        class ResetPassword:
            _base_path = f"{_base_api_path}/auth/reset_password"
            SEND_OTP = f"{_base_path}"
            VERIFY_OTP = f"{_base_path}/verify_otp"

    class Users:
        _base_path = f"{_base_api_path}/users"
        CHECK_USERNAME = f"{_base_path}/check_username"
        GET_BY_ID = f"{_base_path}/{{user_id}}"
        SEARCH = f"{_base_path}/search"
        UPDATE_PROFILE = f"{_base_path}/update_profile"
        UPDATE_PASSWORD = f"{_base_path}/update_password"
        UPDATE_AVATAR = f"{_base_path}/update_avatar"
        DELETE_AVATAR = f"{_base_path}/delete_avatar"
        GET_AVATAR_IMAGE = f"{_base_path}/avatars/{{user_id}}"
        FOLLOW = f"{_base_path}/follow"
        UNFOLLOW = f"{_base_path}/unfollow"
        GET_FOLLOWINGS = f"{_base_path}/followings"
        GET_FOLLOWERS = f"{_base_path}/followers"
        UPDATE_ROLE = f"{_base_path}/update_role"

    class TestUsers:
        _base_path = f"{_base_api_path}/test_users"
        ADMIN_ROLE_TEST = f"{_base_path}/admin_role"
        OWNER_ROLE_TEST = f"{_base_path}/owner_role"

    class ApkUpdates:
        _base_path = f"{_base_api_path}/apk_updates"
        GET_MANY = f"{_base_path}"
        ADD = f"{_base_path}/add"
        GET_ONE = f"{_base_path}/{{update_id}}"
        DELETE = f"{_base_path}/delete"
        DOWNLOAD = f"{_base_path}/download"
