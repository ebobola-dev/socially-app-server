from functools import wraps

from aiohttp.web import Request
from packaging.version import Version

from config.length_requirements import LengthRequirements
from config.re_patterns import RePatterns
from models.avatar_type import AvatarType
from models.exceptions.api_exceptions import UnableToValidateError, ValidationError
from models.gender import Gender
from models.role import Role
from utils.my_validator.exceptions import MyValidatorError
from utils.my_validator.rules import (
    CanCreateInstanceRule,
    DateIsoRule,
    EnumRule,
    IsInstanceRule,
    LengthRule,
    OtpRule,
    ReFullmatchPatternRule,
    ReSearchPatternRule,
    RuleError,
    ValidateRule,
)


class ValidateField:
    def __init__(
        self,
        field_name: str,
        nullable: bool = False,
        required: bool = True,
        rules: list[ValidateRule] = [],
    ):
        self.field_name = field_name
        self.required = required
        self.nullable = nullable
        self.rules = rules

    def __call__(self, value):
        if isinstance(value, str):
            value.strip()
        validate(
            value=value,
            maybe_none=self.nullable,
            rules=self.rules,
            field_name=self.field_name,
        )

    @staticmethod
    def email(field_name: str = "email", required: bool = True, nullable=False):
        return ValidateField(
            field_name=field_name,
            required=required,
            nullable=nullable,
            rules=[
                ReFullmatchPatternRule(
                    re_pattern=RePatterns.EMAIL, error_description="Invalid Email"
                )
            ],
        )

    @staticmethod
    def otp_code(field_name: str = "otp_code", required: bool = True, nullable=False):
        return ValidateField(
            field_name=field_name,
            required=required,
            nullable=nullable,
            rules=[OtpRule()],
        )

    @staticmethod
    def fullname(field_name: str = "fullname", required: bool = False, nullable=False):
        return ValidateField(
            field_name=field_name,
            required=required,
            nullable=nullable,
            rules=[
                IsInstanceRule(str),
                LengthRule(max_length=LengthRequirements.Fullname.MAX),
            ],
        )

    @staticmethod
    def date_of_birth(
        field_name: str = "date_of_birth", required: bool = False, nullable=False
    ):
        return ValidateField(
            field_name=field_name,
            required=required,
            nullable=nullable,
            rules=[
                IsInstanceRule(str),
                DateIsoRule(),
            ],
        )

    @staticmethod
    def gender(field_name: str = "gender", required: bool = False, nullable=True):
        return ValidateField(
            field_name=field_name,
            required=required,
            nullable=nullable,
            rules=[
                EnumRule(Gender),
            ],
        )

    @staticmethod
    def avatar_type(
        field_name: str = "avatar_type", required: bool = True, nullable: bool = False
    ):
        return ValidateField(
            field_name=field_name,
            required=required,
            nullable=nullable,
            rules=[
                EnumRule(AvatarType),
            ],
        )

    @staticmethod
    def role(field_name: str = "role", required: bool = True, nullable: bool = False):
        return ValidateField(
            field_name=field_name,
            required=required,
            nullable=nullable,
            rules=[
                EnumRule(Role),
            ],
        )

    @staticmethod
    def about_me(field_name: str = "about_me", required: bool = False, nullable=False):
        return ValidateField(
            field_name=field_name,
            required=required,
            nullable=nullable,
            rules=[
                IsInstanceRule(str),
                LengthRule(max_length=LengthRequirements.AboutMe.MAX),
            ],
        )

    @staticmethod
    def username(field_name: str = "username", required: bool = True, nullable=False):
        return ValidateField(
            field_name=field_name,
            required=required,
            nullable=nullable,
            rules=[
                IsInstanceRule(str),
                LengthRule(min_length=4, max_length=16),
                ReSearchPatternRule(
                    r"^[a-z0-9._]+$",
                    error_description="only lowercase Latin letters, numbers, underscores and dots are allowed",
                ),
                ReSearchPatternRule(
                    r"^[^.]", error_description="cannot start with a dot"
                ),
                ReSearchPatternRule(
                    r"^[^\d]", error_description="cannot start with a number"
                ),
            ],
        )

    @staticmethod
    def password(field_name: str = "password", required: bool = True, nullable=False):
        return ValidateField(
            field_name=field_name,
            required=required,
            nullable=nullable,
            rules=[
                IsInstanceRule(str),
                ReFullmatchPatternRule(
                    RePatterns.PASSWORD,
                    error_description=LengthRequirements.Password.TEXT,
                ),
            ],
        )

    @staticmethod
    def version(field_name: str = "version", required: bool = True, nullable=False):
        return ValidateField(
            field_name=field_name,
            required=required,
            nullable=nullable,
            rules=[
                CanCreateInstanceRule(Version),
            ],
        )


def validate(
    value: any,
    maybe_none: bool = False,
    rules: list[ValidateRule] = [],
    field_name: str = "value",
):
    if not maybe_none and value is None:
        raise MyValidatorError(["can't be null"], field_name=field_name)
    errors = []
    if value is not None:
        for rule in rules:
            try:
                rule(value)
            except RuleError as rule_error:
                errors.append(rule_error.error_message)
            except Exception as unexcepted_error:
                raise UnableToValidateError(
                    field_name=field_name, error=unexcepted_error
                ) from unexcepted_error
    if errors:
        raise MyValidatorError(
            errors=errors,
            field_name=field_name,
        )


def validate_request_body(*fields: ValidateField):
    def decorator(handler):
        @wraps(handler)
        async def wrapper(self, request: Request):
            validated = {}
            body = await request.json()
            field_specific_errors = {}
            for field in fields:
                key = field.field_name
                was_provided = key in body
                value = body.get(key)
                if isinstance(value, str):
                    value = value.strip()
                try:
                    if was_provided:
                        field(value)
                        validated[key] = value
                    elif field.required:
                        raise MyValidatorError(["must be specified"], field_name=key)
                except MyValidatorError as valid_error:
                    if key not in field_specific_errors:
                        field_specific_errors[key] = []
                    field_specific_errors[key].extend(valid_error.errors)
            if field_specific_errors:
                raise ValidationError(
                    field_specific_erros=field_specific_errors,
                )
            request["validated_body"] = validated
            request["provided_body_keys"] = set(body.keys())
            return await handler(self, request)

        return wrapper

    return decorator
