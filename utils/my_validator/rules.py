from re import fullmatch
from datetime import date, datetime
from abc import ABC, abstractmethod
from typing import Type, TypeVar
from enum import Enum

from models.otp import Otp
from utils.my_validator.exceptions import *

T = TypeVar('T')

class ValidateRule(ABC):
	@abstractmethod
	def __call__(self, value: any) -> any:
		if value is None:
			raise MyValidatorError(["don't call Rule if value is None"])

class LengthRule(ValidateRule):
	def __init__(
		self,
		min_length: int = 0,
		max_length: int | None = None,
	):
		if min_length < 0:
			raise BadInitializeData(f'min_length must be >= 0 (input: {min_length})')
		if max_length is not None and min_length > max_length:
			raise BadInitializeData(f'min_length must be <= max_length (input: {min_length} <-> {max_length})')
		super().__init__()
		self.min_length = min_length
		self.max_length = max_length
		if max_length is not None:
			self.error_description = f"the length of the value must be between {self.min_length} and {self.max_length}"
		else:
			self.error_description = f"the length of the value must be >= {self.min_length}"

	def __call__(self, value):
		super().__call__(value)
		if len(value) < self.min_length:
			raise MyValidatorError([self.error_description])
		if self.max_length is not None and len(value) > self.max_length:
			raise MyValidatorError([self.error_description])

class RePatternRule(ValidateRule):
	def __init__(self, re_pattern, error_description: str = 'invalid_value'):
		super().__init__()
		self.re_pattern = re_pattern
		self.error_description = error_description

	def __call__(self, value):
		super().__call__(value)
		if not fullmatch(self.re_pattern, value):
			raise MyValidatorError([self.error_description])

class OtpRule(ValidateRule):
	def __init__(self):
		super().__init__()

	def __call__(self, value):
		super().__call__(value)
		if not Otp.is_valid_value(value):
			raise MyValidatorError(['Invalid OTP'])

class DateIsoRule(ValidateRule):
	def __init__(self):
		super().__init__()

	def __call__(self, value):
		super().__call__(value)
		try:
			date.fromisoformat(value)
		except:
			raise MyValidatorError(['bad iso date'])

class DateTimeIsoRule(ValidateRule):
	def __init__(self):
		super().__init__()

	def __call__(self, value):
		super().__call__(value)
		try:
			datetime.fromisoformat(value)
		except:
			raise MyValidatorError(['bad iso date'])

class EnumRule(ValidateRule):
	def __init__(self, enum: Type[T]) -> T:
		if not isinstance(enum, type) or not issubclass(enum, Enum):
			raise BadInitializeData(f'EnumRule got wrong type (not Enum): {enum}')
		self.enum_values = tuple(e.value for e in enum)
		if any(map(lambda value: not isinstance(value, int), self.enum_values)):
			raise BadInitializeData('EnumRule can handle only those enums in which all values are [int]')
		super().__init__()
		self.enum = enum
		desc = ''
		for e in enum:
			desc += f'{e.value}({e.name}), '
		self.enum_values_desciption = desc
		self.error_text = f'value must be int or "int" ({self.enum_values_desciption})'

	def __call__(self, value):
		super().__call__(value)
		def check_int(int_value: int):
			if not int_value in self.enum_values:
				raise MyValidatorError([self.error_text])
		temp_value = value
		if not isinstance(temp_value, int | str):
			raise MyValidatorError([self.error_text])
		if isinstance(temp_value, int):
			check_int(temp_value)
			return self.enum(temp_value)
		if isinstance(temp_value, str) and not temp_value.isdigit():
			raise MyValidatorError([self.error_text])
		temp_value = int(temp_value)
		check_int(temp_value)
		return self.enum(temp_value)

class CanCreateInstanceRule(ValidateRule):
	def __init__(self, cls_type: Type[T]) -> T:
		if not isinstance(cls_type, type):
			raise BadInitializeData('[cls_type] must be a type')
		super().__init__()
		self.cls_type = cls_type

	def __call__(self, value):
		super().__call__(value)
		try:
			self.cls_type(value)
		except:
			raise MyValidatorError([f"bad value for {self.cls_type.__name__}"])
