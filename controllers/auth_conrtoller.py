from logging import Logger

from aiohttp.web import Request, Response, json_response
from bcrypt import checkpw

from controllers.middlewares import (
    authenticate,
    content_type_is_json,
    device_id_specified,
)
from controllers.sio_controller import SioController
from models.exceptions.api_exceptions import (
    CouldNotFoundUserWithSpecifiedDataError,
    CouldNotSendOtpToEmailError,
    IncorrectLoginDataError,
    OtpSpamError,
    TryingToResetPasswordWithIncompletedRegistrationError,
    UnauthorizedError,
    ValidationError,
)
from models.otp import OtpDestiny
from repositories.fcm_token_repository import FCMTokenRepository
from repositories.otp_repository import OtpRepository
from repositories.user_repository import UserRepository
from services.email_service import EmailService
from services.tokens_service import TokensService
from utils.my_validator.my_validator import ValidateField, validate_request_body


class AuthConrtoller:
    def __init__(self, logger: Logger, main_sio_namespace: SioController) -> None:
        self._logger = logger
        self._sio = main_sio_namespace

    @content_type_is_json()
    @device_id_specified()
    @validate_request_body(
        ValidateField.username(),
        ValidateField.password(),
        ValidateField.fcm_token(),
    )
    async def login(self, request: Request) -> Response:
        body = request["validated_body"]

        username = body.get("username")
        password = body.get("password")
        fcm_token = body.get("fcm_token")

        user = await UserRepository.get_by_username(request.db_session, username)
        if user is None:
            raise IncorrectLoginDataError(
                server_message=f"Could not found user with username @{username}"
            )

        if not checkpw(password.encode("UTF-8"), user.hashed_password):
            raise IncorrectLoginDataError(
                server_message=f"@{username} gave incorrect password"
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

        if fcm_token:
            await FCMTokenRepository.create_or_update(
                session=request.db_session,
                user_id=user.id,
                device_id=request.device_id,
                new_value=fcm_token,
            )
            self._logger.debug("FCM token is saved")

        self._logger.debug(f"@{username} logged in")

        return json_response(
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user": user.to_json(safe=True, detect_rels_for_user_id=user.id),
            }
        )

    @device_id_specified()
    async def refresh(self, request: Request) -> Response:
        authorization_headers = request.headers.get("authorization")
        if authorization_headers is None:
            raise UnauthorizedError()
        authorization_list = authorization_headers.split(" ")
        if len(authorization_list) < 2:
            raise UnauthorizedError()
        refresh_token = authorization_list[1]
        try:
            refresh_token_data = TokensService.decode_refresh(refresh_token)
        except Exception as _:
            raise UnauthorizedError()
        user_id = refresh_token_data.get("id")

        saved_refresh_token = await TokensService.get_refresh_by_user_and_device_ids(
            session=request.db_session,
            user_id=user_id,
            device_id=request.device_id,
        )

        if saved_refresh_token is None or saved_refresh_token.value != refresh_token:
            raise UnauthorizedError()

        user = await UserRepository.get_by_id_with_relations(
            request.db_session, user_id
        )
        if not user:
            raise UnauthorizedError()

        (
            new_access_token,
            new_refresh_token,
        ) = await TokensService.generate_pair_and_save_refresh(
            session=request.db_session,
            user_id=user.id,
            device_id=request.device_id,
            user_role=user.role,
        )

        self._logger.debug(f"@{user.username} generated new token pair")

        return json_response(
            {
                "access_token": new_access_token,
                "refresh_token": new_refresh_token,
                "user": user.to_json(safe=True, detect_rels_for_user_id=user.id),
            }
        )

    @authenticate()
    @device_id_specified()
    async def logout(self, request: Request) -> Response:
        user = await UserRepository.get_by_id_with_relations(
            request.db_session, request.user_id
        )
        await self._sio.on_logout(user.current_sid)
        await UserRepository.set_current_sid(
            session=request.db_session,
            user_id=user.id,
            new_sid=None,
        )
        await TokensService.delete_refresh(
            session=request.db_session,
            user_id=user.id,
            device_id=request.device_id,
        )
        deleted_fcm_tokens_count = await FCMTokenRepository.delete_by_user(
            session=request.db_session,
            user_id=user.id,
            device_id=request.device_id,
        )
        if deleted_fcm_tokens_count:
            self._logger.debug("FCM token was deleted")
        await request.db_session.commit()
        self._logger.debug(f"@{user.username} has logged out")
        raise UnauthorizedError()

    async def send_otp_to_reset_password(self, request: Request) -> Response:
        #! Need a type:
        #! e - by email
        #! u - by username

        reset_type = request.query.get("type")
        if not isinstance(reset_type, str) or reset_type not in (
            "e",
            "u",
        ):
            raise ValidationError(
                {
                    "type": "must be specified in query ([e] - by email, [u] - by username)",
                }
            )

        user = None
        specified_data = None

        if reset_type == "e":
            email = request.query.get("email")
            ValidateField.email()(email)
            user = await UserRepository.get_by_email(request.db_session, email)
            specified_data = email
        else:
            username = request.query.get("username")
            ValidateField.username()(username)
            user = await UserRepository.get_by_username(request.db_session, username)
            specified_data = username

        if user is None:
            raise CouldNotFoundUserWithSpecifiedDataError(specified_data)

        if not user.is_registration_completed:
            raise TryingToResetPasswordWithIncompletedRegistrationError()

        # * Checking for spam to OTP generation
        if not (await OtpRepository.can_update(request.db_session, user.email_address)):
            raise OtpSpamError(user.email_address)

        # * Updating user OTP
        otp = await OtpRepository.create_or_update(
            request.db_session, user.email_address
        )
        self._logger.info(f"OTP generated: {otp.value}")

        # * Sending OTP to email address
        try:
            await EmailService.send_otp(
                user.email_address, otp.value, OtpDestiny.reset_password
            )
        except Exception:
            raise CouldNotSendOtpToEmailError(user.email_address)

        return json_response(data=otp.to_json(safe=reset_type == "e"))

    @content_type_is_json()
    @device_id_specified()
    @validate_request_body(
        ValidateField.otp_code(),
        ValidateField.fcm_token(),
    )
    async def verify_otp_for_reset_password(self, request: Request) -> Response:
        #! Need a type:
        #! e - by email
        #! u - by username

        reset_type = request.query.get("type")
        if not isinstance(reset_type, str) or reset_type not in (
            "e",
            "u",
        ):
            raise ValidationError(
                {
                    "type": "must be specified in query ([e] - by email, [u] - by username)",
                }
            )

        specified_data = None

        if reset_type == "e":
            email = request.query.get("email")
            ValidateField.email()(email)
            user = await UserRepository.get_by_email(request.db_session, email)
            specified_data = email
        else:
            username = request.query.get("username")
            ValidateField.username()(username)
            user = await UserRepository.get_by_username(request.db_session, username)
            specified_data = username

        if user is None:
            raise CouldNotFoundUserWithSpecifiedDataError(specified_data)

        body = request["validated_body"]
        otp_code = body.get("otp_code")
        fcm_token = body.get("fcm_token")

        await OtpRepository.verify(request.db_session, user.email_address, otp_code)

        self._logger.debug(f"{user.email_address} verified OTP code\n")

        (
            access_token,
            refresh_token,
        ) = await TokensService.generate_pair_and_save_refresh(
            session=request.db_session,
            user_id=user.id,
            device_id=request.device_id,
            user_role=user.role,
        )

        if fcm_token:
            await FCMTokenRepository.create_or_update(
                session=request.db_session,
                user_id=user.id,
                device_id=request.device_id,
                new_value=fcm_token,
            )
            self._logger.debug("FCM token is saved")

        return json_response(
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user": user.to_json(safe=True, detect_rels_for_user_id=user.id),
            }
        )
