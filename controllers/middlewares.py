from functools import wraps
from logging import Logger
from time import time

from aiohttp.web import Request, Response, json_response, middleware
from aiohttp.web_exceptions import HTTPError

from database.database import Database
from models.exceptions.api_exceptions import (
    ApiError,
    BadContentType,
    BadDeviceID,
    ForbiddenForRole,
    IncompleteRegistration,
    UnableToDecodeJsonBody,
    UnauthorizedError,
    ValidationError,
)
from models.role import Role
from repositories.user_repository import UserRepositorty
from services.tokens_service import TokensService
from utils.my_validator.exceptions import MyValidatorError


def _get_access_token_data(authorization_headers: dict | None) -> dict:
    if authorization_headers is None:
        raise UnauthorizedError()
    authorization_list = authorization_headers.split(" ")
    if len(authorization_list) < 2:
        raise UnauthorizedError()

    access_token = authorization_list[1]
    data = TokensService.decode_access(access_token)
    return data


def _get_real_ip(request: Request) -> str:
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    return real_ip or request.remote


def authenticate():
    def decorator(handler):
        @wraps(handler)
        async def wrapper(self, request: Request):
            try:
                data = _get_access_token_data(request.headers.get("authorization"))
                user_id = data.get("id")
                user = await UserRepositorty.get_by_id(request.db_session, user_id)
                if not user:
                    raise UnauthorizedError()
                request.user_id = user_id
                request.user_role = Role(data.get("role"))
            except Exception as _:
                raise UnauthorizedError()
            return await handler(self, request)

        return wrapper

    return decorator


def device_id_specified():
    def decorator(handler):
        @wraps(handler)
        async def wrapper(self, request: Request):
            device_id = request.headers.get("device_id")
            if not isinstance(device_id, str) or not device_id:
                raise BadDeviceID(device_id)
            request.device_id = device_id
            return await handler(self, request)

        return wrapper

    return decorator


def content_type_is_json():
    def decorator(handler):
        @wraps(handler)
        async def wrapper(self, request: Request):
            content_type = request.headers.get("Content-Type")
            if not content_type or content_type != "application/json":
                raise BadContentType(
                    required_type="application/json",
                    input_type=content_type,
                )
            try:
                await request.json()
            except Exception as error:
                raise UnableToDecodeJsonBody(error)
            return await handler(self, request)

        return wrapper

    return decorator


def content_type_is_multipart():
    def decorator(handler):
        @wraps(handler)
        async def wrapper(self, request: Request):
            content_type = request.headers.get("Content-Type")
            if not content_type or not content_type.startswith("multipart/form-data"):
                raise BadContentType(
                    required_type="multipart/form-data",
                    input_type=content_type,
                )
            return await handler(self, request)

        return wrapper

    return decorator


def registration_completed():
    def decorator(handler):
        @wraps(handler)
        async def wrapper(self, request: Request):
            user = await UserRepositorty.get_by_id(request.db_session, request.user_id)
            if not user:
                raise UnauthorizedError()
            if not user.is_registration_completed:
                raise IncompleteRegistration(email=user.email_address)
            return await handler(self, request)

        return wrapper

    return decorator


def owner_role():
    def decorator(handler):
        @wraps(handler)
        async def wrapper(self, request: Request):
            if not request.user_role.is_owner:
                raise ForbiddenForRole(
                    required_role=Role.owner,
                    input_role=request.user_role,
                )
            # ? На всякий случай, ведь я криворукая обезъяна
            existing_owner = await UserRepositorty.get_owner(request.db_session)
            if not existing_owner:
                # self._logger.warning(f'Owner does not exists yet, but user role in token is OWNER')
                raise ForbiddenForRole(
                    required_role=Role.owner,
                    input_role=request.user_role,
                )
            if request.user_id != existing_owner.id:
                # self._logger.warning(f'Real owner id != user id in token, but user role in token is OWNER')
                raise ForbiddenForRole(
                    required_role=Role.owner,
                    input_role=request.user_role,
                )
            return await handler(self, request)

        return wrapper

    return decorator


def admin_role():
    def decorator(handler):
        @wraps(handler)
        async def wrapper(self, request: Request):
            if not request.user_role.is_admin:
                raise ForbiddenForRole(
                    required_role=Role.admin,
                    input_role=request.user_role,
                )
            return await handler(self, request)

        return wrapper

    return decorator


class Middlewares:
    def __init__(self, logger: Logger):
        self._logger = logger

    @middleware
    async def error_middleware(self, request: Request, handler):
        start_time = time()
        ip = _get_real_ip(request)
        try:
            result: Response = await handler(request)
            handle_time = time() - start_time
            self._logger.info(
                f"[{ip}] {request.path} -> {result.status} ({handle_time:.2f} s)\n"
            )
            return result
        except ApiError as api_error:
            handle_time = time() - start_time
            self._logger.error(
                f"[{request.path} -> {api_error.response_status_code} ({handle_time:.2f} s)] {api_error.server_message}\n"
            )
            return json_response(
                status=api_error.response_status_code,
                data=api_error.to_json(),
            )
        except MyValidatorError as my_validator_error:
            handle_time = time() - start_time
            api_error = ValidationError(
                field_specific_erros={
                    my_validator_error.field_name: my_validator_error.errors,
                }
            )
            self._logger.error(
                f"[{request.path} -> {api_error.response_status_code} ({handle_time:.2f} s)] {api_error.server_message}\n"
            )
            return json_response(
                status=api_error.response_status_code,
                data=api_error.to_json(),
            )
        except HTTPError as http_error:
            status_code = 500
            if hasattr(http_error, "status_code"):
                status_code = http_error.status_code
            api_error = ApiError(
                response_status_code=status_code, global_errors=[str(http_error)]
            )
            self._logger.error(
                f"[{request.path} -> {status_code}] {type(http_error).__name__} {http_error}\n"
            )
            return json_response(
                status=api_error.response_status_code,
                data=api_error.to_json(),
            )
        except Exception as unexcepted_error:
            handle_time = time() - start_time
            err = ApiError()
            self._logger.exception(
                f"[{request.path} -> {err.response_status_code} ({handle_time:.2f} s)] Unexcepted error: {unexcepted_error}\n"
            )
            return json_response(
                status=err.response_status_code,
                data=err.to_json(),
            )

    @middleware
    async def database_session(self, request: Request, handler):
        async with Database.session_maker() as session:
            request.db_session = session
            try:
                response = await handler(request)
                await session.commit()
                return response
            except Exception:
                await session.rollback()
                raise
