from models.role import Role
from config.server_config import SERVER_CONFIG
from utils.sizes import SizeUtils
from packaging.version import Version


class ApiError(Exception):
    def __init__(
        self,
        response_status_code: int = 500,
        server_message: str = "Unexcepted server error",
        global_errors: list[str] = ["Something went wrong"],
        field_specific_erros: dict[str, list] = {},
    ):
        super().__init__(server_message)
        self.server_message = f"{type(self).__name__} {server_message}"
        self.response_status_code = response_status_code
        self.global_errors = global_errors
        self.field_specific_erros = field_specific_erros

    def to_json(self):
        json_view = {
            "errors": {
                "_global": self.global_errors,
            }
        }
        for key, value in self.field_specific_erros.items():
            json_view["errors"][key] = value
        return json_view


class UnauthorizedError(ApiError):
    def __init__(self, global_errors=["You are not authorized"]):
        super().__init__(
            response_status_code=401,
            server_message="Could not found or validate access/refresh token",
            global_errors=global_errors,
        )


class ForbiddenError(ApiError):
    def __init__(
        self, server_message="Forbidden", global_errors: list[str] = ["Forbidden"]
    ):
        super().__init__(403, server_message, global_errors)


class ForbiddenForRole(ForbiddenError):
    def __init__(
        self,
        input_role: Role,
        required_role: Role,
    ):
        super().__init__(
            server_message=f"Input role ({input_role.name}), required role: ({required_role.name})",
            global_errors=[f"Required role: {required_role.name}"],
        )


class IncompleteRegistration(ForbiddenError):
    def __init__(self, email):
        super().__init__(
            server_message=f"{email} has not completed registration yet",
            global_errors=["Complete the registration"],
        )


class SpamError(ApiError):
    def __init__(
        self,
        server_message="Got spam",
        global_errors=["Too many requests"],
    ):
        super().__init__(
            response_status_code=429,
            server_message=server_message,
            global_errors=global_errors,
        )


class OtpSpam(SpamError):
    def __init__(self, email_address: str):
        super().__init__(
            server_message=f"Got otp spam from email: {email_address}",
            global_errors=["Wait a minute before resend the OTP code"],
        )


class BadRequest(ApiError):
    def __init__(
        self,
        server_message: str,
        global_errors: list[str] = [],
        field_specific_erros: dict[str, list] = {},
    ):
        gl_errs = global_errors.copy()
        if not gl_errs and not field_specific_erros:
            gl_errs = [server_message]
        super().__init__(
            400,
            server_message,
            gl_errs,
            field_specific_erros=field_specific_erros,
        )


class NotFound(ApiError):
    def __init__(
        self,
        path: str,
    ):
        super().__init__(
            response_status_code=404,
            server_message=f"Trying to {path}",
            global_errors=["404: Not Found"],
        )


class ValidationError(BadRequest):
    def __init__(
        self, field_specific_erros: dict[str, list], server_message: str | None = None
    ):
        super().__init__(
            server_message=server_message or field_specific_erros,
            global_errors=[],
            field_specific_erros=field_specific_erros,
        )


class BadDeviceID(ValidationError):
    def __init__(self, input_device_id, valid_message: str | None = None):
        super().__init__(
            field_specific_erros={
                "device_id": valid_message or "must be specified",
            },
            server_message=f"Bad device id: {input_device_id}",
        )


class BadContentType(BadRequest):
    def __init__(
        self,
        required_type: str,
        input_type: str = "?",
    ):
        super().__init__(
            f"Bad content type: {input_type}, required: {required_type}",
            global_errors=[f'Content-Type must be "{required_type}"'],
        )


class UnableToDecodeJsonBody(BadRequest):
    def __init__(self, error="?"):
        super().__init__(
            server_message=error,
            global_errors=["Bad body"],
        )


class AlreadyFollowing(BadRequest):
    def __init__(self, sub_username, target_username):
        super().__init__(
            server_message=f"@{sub_username} already following @{target_username}",
            global_errors=["You are already following the target user"],
        )


class NotFollowingAnyway(BadRequest):
    def __init__(self, sub_username, target_username):
        super().__init__(
            server_message=f"@{sub_username} not following @{target_username} anyway",
            global_errors=["You are not following the target user anyway"],
        )


class NothingToUpdate(BadRequest):
    def __init__(
        self,
        server_message: str = "Nothing to update",
        global_errors: list[str] = ["Nothing to update"],
    ):
        super().__init__(server_message, global_errors)


class UnableToValidate(ApiError):
    def __init__(self, field_name: str, error):
        super().__init__(
            server_message=f"unable to validate field: {field_name}, {error}",
        )


class OwnerAlreadyRegistered(BadRequest):
    def __init__(self):
        super().__init__("Owner already registered")


class OwnerNotExist(ValidationError):
    def __init__(self):
        super().__init__("Owner does not exist yet")


class ImageIsTooLarge(BadRequest):
    def __init__(self, request_content_length: str):
        str_size = "?"
        if request_content_length.isdigit():
            str_size = SizeUtils.bytes_to_human_readable(int(request_content_length))
        super().__init__(
            f"Image is too large ({str_size})",
            [f"Image is too large (max: {SERVER_CONFIG.MAX_IMAGE_SIZE}MB)"],
        )


class DatabaseError(ApiError):
    def __init__(
        self,
        server_message: str = "Unexcepted database error",
    ):
        super().__init__(500, "Database error: " + server_message)


class CouldNotSendOtpToEmail(BadRequest):
    def __init__(self, email_address, email_error="?"):
        super().__init__(
            server_message=f"Error on sending OTP code to email {email_address}: {email_error}",
            global_errors=[
                "Could not send the OTP code to the specified email address"
            ],
        )


class UserWithEmailHasAlreadyCompletedRegistration(BadRequest):
    def __init__(self, email_address):
        super().__init__(
            server_message=f"User with email ({email_address}) already exists and his registration is completed",
            global_errors=["You are already registered, please log in"],
        )


class CouldNotFoundOtpWithEmail(BadRequest):
    def __init__(self, email_address):
        super().__init__(
            server_message=f"Could not found OTP with email: {email_address}",
            global_errors=["Could not found OTP with your email, resend the otp code"],
        )


class IncorrectOtpCode(BadRequest):
    def __init__(self):
        super().__init__(
            server_message="Incorrect OTP code",
            global_errors=["Incorrect OTP code"],
        )


class CantFollowUnlollowYouself(BadRequest):
    def __init__(self):
        super().__init__(
            server_message="You can't follow(unfollow) to youself",
            global_errors=["You can't follow(unfollow) to youself"],
        )


class OtpCodeIsOutdated(BadRequest):
    def __init__(self):
        super().__init__(
            server_message="The OTP code is outdated",
            global_errors=["Your OTP code is outdated, resend the new OTP code"],
        )


class CouldNotFoundUserWithId(BadRequest):
    def __init__(self, user_id: str):
        super().__init__(
            server_message=f"Could not found user with id ({user_id})",
            global_errors=[f"Could not found user with id ({user_id})"],
        )


class UsernameIsAlreadyTaken(BadRequest):
    def __init__(self, username: str):
        super().__init__(
            server_message=f"Username @{username} is already taken",
            global_errors=[f"Username @{username} is already taken"],
        )


class IncorrectLoginData(BadRequest):
    def __init__(self, server_message: str = "Incorrect login data"):
        super().__init__(
            server_message=server_message,
            global_errors=["Incorrect data"],
        )


class CouldNotFoundUserWithSpecifiedData(BadRequest):
    def __init__(self, specified_data):
        super().__init__(
            server_message=f"Could not found user with specified data ({specified_data})",
            global_errors=[
                f"Could not found user with specified data ({specified_data})"
            ],
        )


class TryingToResetPasswordWithIncompletedRegistration(BadRequest):
    def __init__(self):
        super().__init__(
            server_message="Trying to reset password with incompleted registration",
            global_errors=["You haven't completed registration"],
        )


class AvatarTypeIsNotExternal(BadRequest):
    def __init__(self):
        super().__init__(
            server_message="User avatar type is not external",
            global_errors=["The target user does not have an external avatar image"],
        )


class BadImageFileExt(BadRequest):
    def __init__(self, bad_ext):
        super().__init__(
            server_message=f"Got bad image file ext {bad_ext}",
            global_errors=[
                f"Bad avatar image file ext, allowed: {SERVER_CONFIG.ALLOWED_IMAGE_EXTENSIONS}"
            ],
        )


class CouldNotFoundApkUpdateWithVersion(BadRequest):
    def __init__(self, version: Version):
        super().__init__(f'Could not found apk update with version "{version}"')


class ApkUpdateWithVersionAlreadyExists(BadRequest):
    def __init__(self, version: Version):
        super().__init__(f"Apk update with version ({version}) already exists")


class UserDoesNotHaveExternalAvatarImage(BadRequest):
    def __init__(self, username: str):
        super().__init__(f"Target user does not have an external avatar (@{username})")
