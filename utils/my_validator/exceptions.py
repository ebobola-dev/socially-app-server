class BadInitializeData(Exception):
	def __init__(self, message):
		super().__init__(message)
		self.message = message

class MyValidatorError(Exception):
	def __init__(self, errors: list[str]):
		super().__init__('; '.join(errors))
		self.errors = errors