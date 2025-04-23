from functools import wraps
from aiohttp.web import Request

from utils.my_validator.rules import ValidateRule
from utils.my_validator.exceptions import *

class ValidateField:
	def __init__(
		self,
		field_name: str,
		maybe_none: bool = False,
		rules: list[ValidateRule]  = [],
	):
		self.field_name = field_name
		self.maybe_none = maybe_none
		self.rules = rules

	def __call__(self, value):
		validate(
			value = value,
			maybe_none = self.maybe_none,
			rules = self.rules,
		)

def validate(
	value: any,
	maybe_none: bool = False,
	rules: list[ValidateRule] = [],
):
	if not maybe_none and value == None:
		raise MyValidatorError(["value must be specified and can't be null"])
	if value is not None:
		try:
			for rule in rules:
				rule(value)
		except MyValidatorError:
			raise
		except:
			raise MyValidatorError(["unable to validate"])


def validate_request_body(*fields: ValidateField):
	def decorator(handler):
		@wraps(handler)
		async def wrapper(self, request: Request):
			validated = {}
			body = await request.json()
			errors = []
			for field in fields:
				try:
					value = body.get(field.field_name)
					field(value)
					validated[field.field_name] = value
				except MyValidatorError as valid_error:
					errors.extend(valid_error.errors)
			if errors:
				raise MyValidatorError(errors)
			request['validated_body'] = validated
			return await handler(self, request)
		return wrapper
	return decorator

# def validate_many(*validate_fields: ValidateField):
# 	errors = []
# 	for validate_field in validate_fields:
# 		try:
# 			validate_field()
# 		except MyValidatorError as error:
# 			errors.extend(*(error.errors))
# 	if errors:
# 		raise MyValidatorError(*errors)