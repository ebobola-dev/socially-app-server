import asyncio
from datetime import date
from io import BytesIO
from logging import Logger
from uuid import uuid4

from aiohttp.web import FileResponse, Request, json_response

from config.length_requirements import LengthRequirements
from config.server_config import ServerConfig
from controllers.middlewares import (
    authenticate,
    content_type_is_json,
    content_type_is_multipart,
    owner_role,
)
from controllers.sio_controller import SioController
from models.avatar_type import AvatarType
from models.exceptions.api_exceptions import (
    BadImageFileExtError,
    BadRequestError,
    ImageIsTooLargeError,
    InvalidImageError,
    NothingToUpdateError,
    UnauthorizedError,
    UserDoesNotHaveExternalAvatarImageError,
    UsernameIsAlreadyTakenError,
    UserNotFoundError,
    ValidationError,
)
from models.gender import Gender
from models.pagination import Pagination
from models.role import Role
from repositories.user_repository import UserRepository
from services.file_service import FileService
from services.tokens_service import TokensService
from utils.image_utils import ImageUtils, PillowValidatationResult
from utils.my_validator.my_validator import ValidateField, validate_request_body
from utils.my_validator.rules import LengthRule
from utils.sizes import SizeUtils


class UsersController:
    def __init__(self, logger: Logger, main_sio_namespace: SioController):
        self._logger = logger
        self._sio = main_sio_namespace

    async def check_username(self, request: Request):
        username = request.query.get("username")
        ValidateField.username()(username)

        user = await UserRepository.get_by_username(request.db_session, username)
        self._logger.debug(
            f"@{username} is {'not exists' if user is None else 'exists'}\n"
        )
        return json_response(data={"is_exists": user is not None})

    @authenticate()
    async def get_by_id(self, request: Request):
        user_id = request.match_info["user_id"]
        user = await UserRepository.get_by_id_with_relations(request.db_session, user_id, include_deleted=True)
        if user is None:
            raise UserNotFoundError(user_id)
        return json_response(data=user.to_json(safe=user_id == request.user_id))

    @authenticate()
    async def search(self, request: Request):
        pagination = Pagination.from_request(request)
        search_data = request.query.get("search_data", None)
        ValidateField(
            field_name="search_data",
            nullable=False,
            rules=[LengthRule(max_length=LengthRequirements.Fullname.MAX)],
        )(search_data)
        search_data = search_data.strip()

        result = await UserRepository.find_by_pattern(
            session=request.db_session,
            pattern=search_data,
            pagination=pagination,
            ignore_id=request.user_id,
        )

        result_json = tuple(map(lambda user: user.to_json(short=True), result))

        return json_response(
            data={
                "count": len(result),
                "pagination": {
                    "page": pagination.page,
                    "per_page": pagination.per_page,
                },
                "users": result_json,
            }
        )

    @authenticate()
    @content_type_is_json()
    @validate_request_body(
        ValidateField.fullname(required=False),
        ValidateField.username(required=False),
        ValidateField.gender(required=False),
        ValidateField.date_of_birth(required=False),
        ValidateField.about_me(required=False),
    )
    async def update_profile(self, request: Request):
        user = await UserRepository.get_by_id_with_relations(request.db_session, request.user_id)
        body: dict = request["validated_body"]
        fullname = body.get("fullname")
        username = body.get("username")
        gender = body.get("gender")
        date_of_birth = body.get("date_of_birth")
        about_me = body.get("about_me")
        is_gender_specifed = "gender" in request["provided_body_keys"]

        new_data = dict()

        if fullname is not None and user.fullname != fullname:
            new_data["fullname"] = fullname

        if username and username != user.username:
            user_with_username = await UserRepository.get_by_username(
                request.db_session, username
            )
            if user_with_username:
                raise UsernameIsAlreadyTakenError(username)
            new_data["username"] = username

        if gender:
            gender = Gender(gender)
            if gender != user.gender:
                new_data["gender"] = gender
        elif is_gender_specifed and user.gender is not None:
            new_data["gender"] = None

        if date_of_birth and user.date_of_birth != date_of_birth:
            date_of_birth = date.fromisoformat(date_of_birth)
            different_time = date.today() - date_of_birth
            if different_time.days <= 0:
                raise ValidationError({"date_of_birth": "must be day before today"})
            new_data["date_of_birth"] = date_of_birth

        if about_me is not None and user.about_me != about_me:
            new_data["about_me"] = about_me

        if not new_data:
            raise NothingToUpdateError(
                server_message=f"nothing to update, new_data: {new_data}",
            )

        self._logger.debug(f"{user.email_address} will changed: {new_data}")

        updated_user = await UserRepository.update_(
            request.db_session, user.id, new_data
        )

        return json_response({"updated_user": updated_user.to_json(safe=True)})

    @authenticate()
    @content_type_is_json()
    @validate_request_body(ValidateField.password(field_name="new_password"))
    async def update_password(self, request: Request):
        user = await UserRepository.get_by_id_with_relations(request.db_session, request.user_id)
        body: dict = request["validated_body"]
        new_password = body.get("new_password")
        await UserRepository.update_password(request.db_session, user.id, new_password)
        self._logger.debug(f"Password updated [{user.email_address}]")
        return json_response()

    @authenticate()
    @content_type_is_multipart()
    async def update_avatar(self, request: Request):
        user = await UserRepository.get_by_id_with_relations(request.db_session, request.user_id)
        content_length = request.headers.get("Content-Length")
        try:
            int_length = int(content_length)
            self._logger.debug(
                f"(update_avatar) got request {SizeUtils.bytes_to_human_readable(int_length)}"
            )
        except Exception as _:
            self._logger.debug(
                f"(update_avatar) got request content_length: {content_length}"
            )

        reader = await request.multipart()

        avatar_file_buffer = None
        file_ext = None
        filename = None
        avatar_type = None

        async for part in reader:
            match part.name:
                case "avatar":
                    filename = part.filename
                    if filename is None or filename == "":
                        raise ValidationError(
                            {
                                "avatar": "must be a file",
                            }
                        )
                    file_ext = filename[filename.rfind(".") :]
                    if (
                        not file_ext
                        or file_ext == "."
                        or file_ext[1:] not in ServerConfig.ALLOWED_IMAGE_EXTENSIONS
                    ):
                        raise BadImageFileExtError(file_ext)
                    avatar_file_buffer = BytesIO()
                    total_size = 0
                    while chunk := await part.read_chunk(4096):
                        total_size += len(chunk)
                        if total_size > ServerConfig.MAX_IMAGE_SIZE * 1024 * 1024:
                            raise ImageIsTooLargeError(content_length)
                        avatar_file_buffer.write(chunk)
                    avatar_file_buffer.seek(0)
                case "avatar_type":
                    avatar_type = (await part.text()).strip()

        ValidateField.avatar_type()(avatar_type)

        avatar_type = AvatarType(int(avatar_type))

        if avatar_type == AvatarType.external:
            if not avatar_file_buffer:
                raise ValidationError(
                    {"avatar": "file must be specified if avatar_type is external"}
                )
            pillow_validation_result = await asyncio.to_thread(
                ImageUtils.is_valid_by_pillow, avatar_file_buffer
            )
            is_valid_by_filetype = await asyncio.to_thread(
                ImageUtils.is_valid_by_filetype, avatar_file_buffer
            )
            self._logger.debug(
                f"(update avatar) is valid by filetype: {is_valid_by_filetype}"
            )
            if pillow_validation_result == PillowValidatationResult.unable:
                self._logger.warning(
                    "(update avatar) pillow cannot determine the image format"
                )
            else:
                self._logger.debug(
                    f"(update avatar) is valid by pillow: {pillow_validation_result.name}"
                )
            if not (
                pillow_validation_result != PillowValidatationResult.invalid
                and is_valid_by_filetype
            ):
                raise InvalidImageError(field_name='avatar', filename=filename)
            avatar_id = uuid4()
            if user.avatar_id is not None:
                await FileService.delete_avatar(user.id)
            await FileService.save_avatar(
                user_id=user.id,
                avatar_bytes=avatar_file_buffer,
                avatar_filename_ext=file_ext[1:],
            )
            updated_user = await UserRepository.update_avatar(
                session=request.db_session,
                user_id=user.id,
                new_avatar_type=avatar_type,
                new_avatar_id=avatar_id,
            )
            self._logger.debug(f"(update avatar) @{user.username} uploaded new avatar")
            return json_response(data={"updated_user": updated_user.to_json(safe=True)})
        else:
            if user.avatar_type is AvatarType.external:
                await FileService.delete_avatar(user.id)
            updated_user = await UserRepository.update_avatar(
                session=request.db_session,
                user_id=user.id,
                new_avatar_type=avatar_type,
            )
            self._logger.debug(f"@{user.username} changed avatar to {avatar_type}")
            return json_response(data={"updated_user": updated_user.to_json(safe=True)})

    @authenticate()
    async def delete_avatar(self, request: Request):
        user_id = request.user_id
        saved_user = await UserRepository.get_by_id_with_relations(request.db_session, user_id)
        if not saved_user:
            raise UserNotFoundError(user_id)
        updated_user = await UserRepository.delete_avatar(request.db_session, user_id)
        await FileService.delete_avatar(user_id)
        self._logger.debug(f"@{saved_user.username} deleted avatar")
        return json_response(data={"updated_user": updated_user.to_json(safe=True)})

    async def get_avatar_image(self, request: Request):
        user_id = request.match_info.get("user_id")
        target_user = await UserRepository.get_by_id_with_relations(request.db_session, user_id)
        if not target_user:
            raise UserNotFoundError(user_id)
        if not target_user.avatar_id or target_user.avatar_type != AvatarType.external:
            raise UserDoesNotHaveExternalAvatarImageError(target_user.username)
        avatar_file_path = await FileService.get_avatar_filepath(user_id)
        if avatar_file_path is None:
            self._logger.warning(
                f"Unable to find avatar file path for @{target_user.username}, but its exists in database"
            )
            raise UserDoesNotHaveExternalAvatarImageError(target_user.username)
        return FileResponse(avatar_file_path)

    @authenticate()
    async def follow(self, request: Request):
        user_id = request.user_id
        target_id = request.query.get("target_id")
        if not target_id:
            raise ValidationError(
                {
                    "target_id": "must be specified in query",
                }
            )
        updated_user = await UserRepository.follow(
            request.db_session, user_id, target_id
        )

        target_user = await UserRepository.get_by_id_with_relations(request.db_session, target_id)
        if target_user.current_sid:
            await self._sio.emit_new_follower(
                target_sid=target_user.current_sid,
                follower_id=user_id,
                follower_username=updated_user.username,
            )
        return json_response({"updated_user": updated_user.to_json(safe=True)})

    @authenticate()
    async def unfollow(self, request: Request):
        user_id = request.user_id
        target_id = request.query.get("target_id")
        if not target_id:
            raise ValidationError(
                {
                    "target_id": "must be specified in query",
                }
            )
        updated_user = await UserRepository.unfollow(
            request.db_session, user_id, target_id
        )
        return json_response({"updated_user": updated_user.to_json(safe=True)})

    @authenticate()
    async def get_followings(self, request: Request):
        target_id = request.query.get("target_id")
        pagination = Pagination.from_request(request)
        if not target_id:
            raise ValidationError(
                {
                    "target_id": "must be specified in query",
                }
            )
        target_followings = await UserRepository.get_followings(
            request.db_session, target_id, pagination
        )
        self._logger.debug(
            f"(get followings) page: {pagination.page}, limit: {pagination.per_page}, result count: {len(target_followings)}"
        )
        return json_response(
            data={
                "count": len(target_followings),
                "pagination": {
                    "page": pagination.page,
                    "per_page": pagination.per_page,
                },
                "followings": list(
                    map(lambda u: u.to_json(short=True), target_followings)
                ),
            }
        )

    @authenticate()
    async def get_followers(self, request: Request):
        target_id = request.query.get("target_id")
        pagination = Pagination.from_request(request)
        if not target_id:
            raise ValidationError(
                {
                    "target_id": "must be specified in query",
                }
            )
        target_followers = await UserRepository.get_followers(
            request.db_session, target_id, pagination
        )
        self._logger.debug(
            f"(get followers) page: {pagination.page}, limit: {pagination.per_page}, result count: {len(target_followers)}"
        )
        return json_response(
            data={
                "count": len(target_followers),
                "pagination": {
                    "page": pagination.page,
                    "per_page": pagination.per_page,
                },
                "followers": list(
                    map(lambda u: u.to_json(short=True), target_followers)
                ),
            }
        )

    @authenticate()
    @owner_role()
    async def update_role(self, request: Request):
        target_id = request.query.get("target_id")
        new_role = request.query.get("new_role")
        # * Validation
        if not target_id:
            raise ValidationError(
                {
                    "target_id": "must be specified in query",
                }
            )
        ValidateField.role(field_name="new_role")(new_role)
        new_role = Role(int(new_role))
        if new_role == Role.owner:
            raise BadRequestError(
                "You can not upgrade role to OWNER using this request"
            )
        target_user = await UserRepository.get_by_id_with_relations(request.db_session, target_id)
        if not target_user:
            raise UserNotFoundError(target_id)
        if request.user_id == target_id:
            raise BadRequestError("You cannot update the role for youself")
        if not target_user.is_registration_completed:
            raise BadRequestError("The target user has not completed registration yet")
        # * End validation
        await UserRepository.update_role(
            request.db_session,
            target_id=target_id,
            new_role=new_role,
        )
        owner = await UserRepository.get_owner(request.db_session)
        self._logger.warning(
            f"OWNER({owner.username}) updated role for @{target_user.username} to ({new_role.name})"
        )
        return json_response()

    @authenticate()
    async def soft_delete(self, request: Request):
        user = await UserRepository.get_by_id(request.db_session, request.user_id)
        if user is None:
            raise UserNotFoundError(request.user_id)
        user_sid = user.current_sid
        await UserRepository.soft_delete(
            session=request.db_session, target_id=user.id
        )
        await self._sio.on_user_deleted(user_sid)
        await TokensService.delete_all_by_user_id(
            session=request.db_session, user_id=user.id
        )
        await request.db_session.commit()
        self._logger.warning(f"User (@{user.username}) has been deleted (by himself)\n")
        raise UnauthorizedError()
