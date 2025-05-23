from datetime import date
from logging import Logger

from aiohttp.web import Request, json_response

from config.server_config import ServerConfig
from controllers.middlewares import (
    authenticate,
    content_type_is_json,
    device_id_specified,
)
from models.exceptions.api_exceptions import (
    CouldNotSendOtpToEmailError,
    OtpSpamError,
    UsernameIsAlreadyTakenError,
    UserNotFoundError,
    UserWithEmailHasAlreadyCompletedRegistrationError,
    ValidationError,
)
from models.gender import Gender
from models.otp import OtpDestiny
from models.role import Role
from repositories.otp_repository import OtpRepository
from repositories.user_repository import UserRepository
from services.email_service import EmailService
from services.tokens_service import TokensService
from utils.my_validator.my_validator import ValidateField, validate_request_body


class RegistrationController:
    def __init__(self, logger: Logger):
        self._logger = logger

    @content_type_is_json()
    @validate_request_body(
        ValidateField.email(),
    )
    async def check_email(self, request: Request):
        email = request["validated_body"]["email"]

        # * Checking for spam to OTP generation
        if not (await OtpRepository.can_update(request.db_session, email)):
            raise OtpSpamError(email)

        # * Check user exists
        user = await UserRepository.get_by_email(request.db_session, email)
        if user is not None and user.is_registration_completed:
            raise UserWithEmailHasAlreadyCompletedRegistrationError(email_address=email)

        # * Creating and saving OTP
        otp = await OtpRepository.create_or_update(request.db_session, email)
        self._logger.info(f"{email} OTP generated: {otp.value}")

        # * Sending OTP to email address
        try:
            await EmailService.send_otp(email, otp.value, OtpDestiny.registration)
        except Exception as email_error:
            raise CouldNotSendOtpToEmailError(email, email_error)

        return json_response(data=otp.to_json(safe=True))

    @content_type_is_json()
    @device_id_specified()
    @validate_request_body(
        ValidateField.email(),
        ValidateField.otp_code(),
        ValidateField(field_name="owner_key", required=False, nullable=True),
    )
    async def check_otp(self, request: Request):
        body: dict = request["validated_body"]
        email = body.get("email")

        # * Check user with registration completed
        user = await UserRepository.get_by_email(request.db_session, email)
        if user is not None and user.is_registration_completed:
            raise UserWithEmailHasAlreadyCompletedRegistrationError(email_address=email)

        otp_code = body.get("otp_code")

        await OtpRepository.verify(request.db_session, email, otp_code)

        self._logger.debug(f"{email} verified OTP code")

        owner_key = body.get("owner_key")

        if user is None:
            new_user_role = Role.user
            if (
                owner_key
                and ServerConfig.OWNER_KEY
                and ServerConfig.OWNER_KEY == owner_key
            ):
                new_user_role = Role.owner
            user = await UserRepository.create_new(
                request.db_session, email, new_user_role
            )
            if new_user_role == Role.owner:
                self._logger.warning(f"OWNER user has registered, email: {email}")
        else:
            if user.role != Role.owner:
                if (
                    owner_key
                    and ServerConfig.OWNER_KEY
                    and ServerConfig.OWNER_KEY == owner_key
                ):
                    user = await UserRepository.update_role(
                        request.db_session,
                        target_id=user.id,
                        new_role=Role.owner,
                    )
                    self._logger.warning(
                        f"OWNER user has registered(role updated), email: {email}"
                    )

        (
            access_token,
            refresh_token,
        ) = await TokensService.generate_pair_and_save_refresh(
            session=request.db_session,
            user_id=user.id,
            device_id=request.device_id,
            user_role=user.role,
        )

        return json_response(
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user_id": user.id,
                "user_role": user.role.value,
            }
        )

    @authenticate()
    @content_type_is_json()
    @validate_request_body(
        ValidateField.fullname(),
        ValidateField.date_of_birth(),
        ValidateField.gender(),
        ValidateField.about_me(),
        ValidateField.username(),
        ValidateField.password(),
    )
    async def complete_registration(self, request: Request):
        body: dict = request["validated_body"]

        fullname = body.get("fullname")
        date_of_birth = body.get("date_of_birth")
        gender = body.get("gender")
        about_me = body.get("about_me")
        username = body.get("username")
        password = body.get("password")

        date_of_birth = date.fromisoformat(date_of_birth)

        different_time = date.today() - date_of_birth
        if different_time.days <= 0:
            raise ValidationError({"date_of_birth": "must be day before today"})

        if gender is not None:
            gender = Gender(gender)

        # * Find the user by id
        user_id = request.user_id

        user = await UserRepository.get_by_id_with_relations(request.db_session, user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        if user is not None and user.is_registration_completed:
            raise UserWithEmailHasAlreadyCompletedRegistrationError(user.email_address)

        # * Check username is unique
        if (
            await UserRepository.get_by_username(request.db_session, username)
            is not None
        ):
            raise UsernameIsAlreadyTakenError(username)

        # * Completing registration
        updated_user = await UserRepository.complete_registration(
            session=request.db_session,
            user_id=user_id,
            fullname=fullname,
            gender=gender,
            date_of_birth=date_of_birth,
            about_me=about_me,
            username=username,
            password=password,
        )
        self._logger.debug(f"{user.email_address} completed the registration")
        return json_response(data=updated_user.to_json(safe=True, detect_rels_for_user_id=updated_user.id))
