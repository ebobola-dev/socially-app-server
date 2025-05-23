from packaging.version import Version

from config.server_config import ServerConfig
from models.exceptions.api_conflict_type import ApiConflictType
from models.role import Role
from utils.sizes import SizeUtils


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


class ForbiddenForRoleError(ForbiddenError):
    def __init__(
        self,
        input_role: Role,
        required_role: Role,
    ):
        super().__init__(
            server_message=f"Input role ({input_role.name}), required role: ({required_role.name})",
            global_errors=[f"Required role: {required_role.name}"],
        )


class IncompleteRegistrationError(ForbiddenError):
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


class OtpSpamError(SpamError):
    def __init__(self, email_address: str):
        super().__init__(
            server_message=f"Got otp spam from email: {email_address}",
            global_errors=["Wait a minute before resend the OTP code"],
        )


class BadRequestError(ApiError):
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


class NotFoundError(ApiError):
    def __init__(
        self,
        path: str,
    ):
        super().__init__(
            response_status_code=404,
            server_message=f"Trying to {path}",
            global_errors=["404: Not Found"],
        )


class ValidationError(BadRequestError):
    def __init__(
        self, field_specific_erros: dict[str, list], server_message: str | None = None
    ):
        super().__init__(
            server_message=server_message or field_specific_erros,
            global_errors=[],
            field_specific_erros=field_specific_erros,
        )


class BadDeviceIDError(ValidationError):
    def __init__(self, input_device_id, valid_message: str | None = None):
        super().__init__(
            field_specific_erros={
                "device_id": valid_message or "must be specified",
            },
            server_message=f"Bad device id: {input_device_id}",
        )


class BadContentTypeError(BadRequestError):
    def __init__(
        self,
        required_type: str,
        input_type: str = "?",
    ):
        super().__init__(
            f"Bad content type: {input_type}, required: {required_type}",
            global_errors=[f'Content-Type must be "{required_type}"'],
        )


class UnableToDecodeJsonBodyError(BadRequestError):
    def __init__(self, error="?"):
        super().__init__(
            server_message=error,
            global_errors=["Bad body"],
        )


class ConflictError(ApiError):
    def __init__(
        self, conflict_type: ApiConflictType, server_message: str = "CONFLICT"
    ):
        super().__init__(
            response_status_code=409,
            server_message=server_message,
            field_specific_erros={
                "conflict_type": conflict_type.name,
            },
            global_errors=[],
        )


class AlreadyFollowingError(ConflictError):
    def __init__(self, sub_username, target_username):
        super().__init__(
            conflict_type=ApiConflictType.ALREADY_FOLLOWING,
            server_message=f"@{sub_username} already following @{target_username}",
        )


class NotFollowingAnywayError(ConflictError):
    def __init__(self, sub_username, target_username):
        super().__init__(
            conflict_type=ApiConflictType.NOT_FOLLWING,
            server_message=f"@{sub_username} not following @{target_username} anyway",
        )


class NothingToUpdateError(BadRequestError):
    def __init__(
        self,
        server_message: str = "Nothing to update",
        global_errors: list[str] = ["Nothing to update"],
    ):
        super().__init__(server_message, global_errors)


class UnableToValidateError(ApiError):
    def __init__(self, field_name: str, error):
        super().__init__(
            server_message=f"unable to validate field: {field_name}, {error}",
        )


class OwnerAlreadyRegisteredError(BadRequestError):
    def __init__(self):
        super().__init__("Owner already registered")


class OwnerNotExistError(ValidationError):
    def __init__(self):
        super().__init__("Owner does not exist yet")


class ImageIsTooLargeError(BadRequestError):
    def __init__(self, request_content_length: str = "?"):
        str_size = "?"
        if request_content_length.isdigit():
            str_size = SizeUtils.bytes_to_human_readable(int(request_content_length))
        super().__init__(
            f"Image is too large ({str_size})",
            [f"Image is too large (max: {ServerConfig.MAX_IMAGE_SIZE}MB)"],
        )


class DatabaseError(ApiError):
    def __init__(
        self,
        server_message: str = "Unexcepted database error",
    ):
        super().__init__(500, "Database error: " + server_message)


class CouldNotSendOtpToEmailError(BadRequestError):
    def __init__(self, email_address, email_error="?"):
        super().__init__(
            server_message=f"Error on sending OTP code to email {email_address}: {email_error}",
            global_errors=[
                "Could not send the OTP code to the specified email address"
            ],
        )


class UserWithEmailHasAlreadyCompletedRegistrationError(BadRequestError):
    def __init__(self, email_address):
        super().__init__(
            server_message=f"User with email ({email_address}) already exists and his registration is completed",
            global_errors=["You are already registered, please log in"],
        )


class CouldNotFoundOtpWithEmailError(BadRequestError):
    def __init__(self, email_address):
        super().__init__(
            server_message=f"Could not found OTP with email: {email_address}",
            global_errors=["Could not found OTP with your email, resend the otp code"],
        )


class IncorrectOtpCodeError(BadRequestError):
    def __init__(self):
        super().__init__(
            server_message="Incorrect OTP code",
            global_errors=["Incorrect OTP code"],
        )


class CantFollowUnlollowYouselfError(BadRequestError):
    def __init__(self):
        super().__init__(
            server_message="You can't follow(unfollow) to youself",
            global_errors=["You can't follow(unfollow) to youself"],
        )


class OtpCodeIsOutdatedError(BadRequestError):
    def __init__(self):
        super().__init__(
            server_message="The OTP code is outdated",
            global_errors=["Your OTP code is outdated, resend the new OTP code"],
        )


class UserNotFoundError(BadRequestError):
    def __init__(self, user_id: str):
        super().__init__(
            server_message=f"Could not found user with id ({user_id})",
            global_errors=["User not found"],
        )


class UserDeletedError(BadRequestError):
    def __init__(self, user_id: str):
        super().__init__(
            server_message=f"User({user_id}) deleted",
            global_errors=["User deleted"],
        )


class UsernameIsAlreadyTakenError(BadRequestError):
    def __init__(self, username: str):
        super().__init__(
            server_message=f"Username @{username} is already taken",
            global_errors=[f"Username @{username} is already taken"],
        )


class IncorrectLoginDataError(BadRequestError):
    def __init__(self, server_message: str = "Incorrect login data"):
        super().__init__(
            server_message=server_message,
            global_errors=["Incorrect data"],
        )


class CouldNotFoundUserWithSpecifiedDataError(BadRequestError):
    def __init__(self, specified_data):
        super().__init__(
            server_message=f"Could not found user with specified data ({specified_data})",
            global_errors=[
                f"Could not found user with specified data ({specified_data})"
            ],
        )


class TryingToResetPasswordWithIncompletedRegistrationError(BadRequestError):
    def __init__(self):
        super().__init__(
            server_message="Trying to reset password with incompleted registration",
            global_errors=["You haven't completed registration"],
        )


class AvatarTypeIsNotExternalError(BadRequestError):
    def __init__(self):
        super().__init__(
            server_message="User avatar type is not external",
            global_errors=["The target user does not have an external avatar image"],
        )


class BadImageFileExtError(BadRequestError):
    def __init__(self, bad_ext):
        super().__init__(
            server_message=f"Got bad image file ext {bad_ext}",
            global_errors=[
                f"Bad avatar image file ext({bad_ext}), allowed: {ServerConfig.ALLOWED_IMAGE_EXTENSIONS}"
            ],
        )


class CouldNotFoundApkUpdateWithVersionError(BadRequestError):
    def __init__(self, version: Version):
        super().__init__(f'Could not found apk update with version "{version}"')


class ApkUpdateWithVersionAlreadyExistsError(BadRequestError):
    def __init__(self, version: Version):
        super().__init__(f"Apk update with version ({version}) already exists")


class UserDoesNotHaveExternalAvatarImageError(BadRequestError):
    def __init__(self, username: str):
        super().__init__(f"Target user does not have an external avatar (@{username})")


class PostNoImagesError(BadRequestError):
    def __init__(self):
        super().__init__("The post must contain at least one image")


class ToManyImagesInPostError(BadRequestError):
    def __init__(self):
        super().__init__(
            f"Post can contain no more that {ServerConfig.MAX_IMAGES_IN_POST} images"
        )


class ToManyImagesInMessageError(BadRequestError):
    def __init__(self):
        super().__init__(
            f"Message can contain no more that {ServerConfig.MAX_IMAGES_IN_MESSAGE} images"
        )


class PostNotFoundError(BadRequestError):
    def __init__(self, post_id: str):
        super().__init__(
            server_message=f"Could not found post with id ({post_id})",
            global_errors=["Post not found"],
        )


class PostIdNotSpecifiedError(ValidationError):
    def __init__(
        self,
        field_name: str = "post_id",
        error_text: str = "must be specified in query",
    ):
        fc_error = {field_name: error_text}
        super().__init__(field_specific_erros=fc_error)


class CommentIdNotSpecifiedError(ValidationError):
    def __init__(
        self,
        field_name: str = "comment_id",
        error_text: str = "must be specified in query",
    ):
        fc_error = {field_name: error_text}
        super().__init__(field_specific_erros=fc_error)


class InvalidImageError(ValidationError):
    def __init__(self, filename: str, field_name: str = "image"):
        fc_error = {field_name: f"invalid image file ({filename})"}
        super().__init__(fc_error)


class AlreadyLikedError(ConflictError):
    def __init__(self, user_id: str, post_id: str):
        super().__init__(
            conflict_type=ApiConflictType.ALREADY_LIKED,
            server_message=f"User({user_id}) already liked post({post_id})",
        )


class NotLikedAnywayError(ConflictError):
    def __init__(self, user_id: str, post_id: str):
        super().__init__(
            conflict_type=ApiConflictType.NOT_LIKED,
            server_message=f"User({user_id}) not liked post({post_id}) anyway",
        )


class CommentNotFoundError(BadRequestError):
    def __init__(self, comment_id: str):
        super().__init__(
            server_message=f"Could not found comment with id ({comment_id})",
            global_errors=["Comment not found"],
        )


class ForbiddenToDeleteCommentError(ForbiddenError):
    def __init__(self, one_global_error="You can't delete someone else's comment"):
        super().__init__("Forbidden to delete comment", [one_global_error])


class MinioNotFoundError(ApiError):
    def __init__(self, key: str = "was not specified"):
        super().__init__(
            response_status_code=404,
            server_message=f"Minio could't found file by key: {key}",
            global_errors=["File not found"],
        )


class MinioError(ApiError):
    def __init__(
        self,
        error: str | object = "was not specified",
    ):
        super().__init__(
            server_message=f"Minio error: {error}",
        )
