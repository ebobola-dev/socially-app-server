from abc import ABC, abstractmethod
from datetime import date, datetime
from enum import Enum
from re import fullmatch, search
from typing import Type, TypeVar

from models.otp import Otp
from utils.my_validator.exceptions import BadInitializeDataError

T = TypeVar("T")


class RuleError(Exception):
    def __init__(self, error):
        super().__init__(error)
        self.error_message = error


class ValidateRule(ABC):
    @abstractmethod
    def __call__(self, value: any) -> any:
        if value is None:
            raise RuleError("don't call Rule if value is None")


class LengthRule(ValidateRule):
    def __init__(
        self,
        min_length: int = 0,
        max_length: int | None = None,
    ):
        if min_length < 0:
            raise BadInitializeDataError(f"min_length must be >= 0 (input: {min_length})")
        if max_length is not None and min_length > max_length:
            raise BadInitializeDataError(
                f"min_length must be <= max_length (input: {min_length} <-> {max_length})"
            )
        super().__init__()
        self.min_length = min_length
        self.max_length = max_length
        if max_length is not None:
            self.error_description = f"the length of the value must be between {self.min_length} and {self.max_length}"
        else:
            self.error_description = (
                f"the length of the value must be >= {self.min_length}"
            )

    def __call__(self, value):
        super().__call__(value)
        if len(value) < self.min_length:
            raise RuleError(self.error_description)
        if self.max_length is not None and len(value) > self.max_length:
            raise RuleError(self.error_description)


class ReFullmatchPatternRule(ValidateRule):
    def __init__(self, re_pattern, error_description: str = "invalid_value"):
        super().__init__()
        self.re_pattern = re_pattern
        self.error_description = error_description

    def __call__(self, value):
        super().__call__(value)
        if not fullmatch(self.re_pattern, value):
            raise RuleError(self.error_description)


class ReSearchPatternRule(ValidateRule):
    def __init__(self, re_pattern, error_description: str = "invalid_value"):
        super().__init__()
        self.re_pattern = re_pattern
        self.error_description = error_description

    def __call__(self, value):
        super().__call__(value)
        if not search(self.re_pattern, value):
            raise RuleError(self.error_description)


class OtpRule(ValidateRule):
    def __init__(self):
        super().__init__()

    def __call__(self, value):
        super().__call__(value)
        if not Otp.is_valid_value(value):
            raise RuleError("Invalid OTP")


class DateIsoRule(ValidateRule):
    def __init__(self):
        super().__init__()

    def __call__(self, value):
        super().__call__(value)
        try:
            date.fromisoformat(value)
        except Exception as _:
            raise RuleError("bad iso date")


class DateTimeIsoRule(ValidateRule):
    def __init__(self):
        super().__init__()

    def __call__(self, value):
        super().__call__(value)
        try:
            datetime.fromisoformat(value)
        except Exception as _:
            raise RuleError("bad iso datetime")


class EnumRule(ValidateRule):
    def __init__(self, enum: Type[T]) -> T:
        if not isinstance(enum, type) or not issubclass(enum, Enum):
            raise BadInitializeDataError(f"EnumRule got wrong type (not Enum): {enum}")
        self.enum_values = tuple(e.value for e in enum)
        if any(map(lambda value: not isinstance(value, int), self.enum_values)):
            raise BadInitializeDataError(
                "EnumRule can handle only those enums in which all values are [int]"
            )
        super().__init__()
        self.enum = enum
        desc = ""
        for e in enum:
            desc += f"{e.value}({e.name}), "
        self.enum_values_desciption = desc
        self.error_text = f'value must be int or "int" ({self.enum_values_desciption})'

    def __call__(self, value):
        super().__call__(value)

        def check_int(int_value: int):
            if int_value not in self.enum_values:
                raise RuleError(self.error_text)

        temp_value = value
        if not isinstance(temp_value, int | str):
            raise RuleError(self.error_text)
        if isinstance(temp_value, int):
            check_int(temp_value)
            return self.enum(temp_value)
        if isinstance(temp_value, str) and not temp_value.isdigit():
            raise RuleError(self.error_text)
        temp_value = int(temp_value)
        check_int(temp_value)
        return self.enum(temp_value)


class CanCreateInstanceRule(ValidateRule):
    def __init__(self, cls_type: Type[T]) -> T:
        if not isinstance(cls_type, type):
            raise BadInitializeDataError("[cls_type] must be a type")
        super().__init__()
        self.cls_type = cls_type

    def __call__(self, value):
        super().__call__(value)
        try:
            self.cls_type(value)
        except Exception as _:
            raise RuleError(f"bad value for {self.cls_type.__name__}")


class IsInstanceRule(ValidateRule):
    def __init__(self, *types: Type):
        if not types:
            raise BadInitializeDataError("At least one type must be specified")
        if not all(isinstance(t, type) for t in types):
            raise BadInitializeDataError("All arguments must be types")
        self.types = types
        self.type_names = ", ".join(t.__name__ for t in types)
        super().__init__()

    def __call__(self, value):
        super().__call__(value)
        if not isinstance(value, self.types):
            raise RuleError(f"Value must be instance of: {self.type_names}")
