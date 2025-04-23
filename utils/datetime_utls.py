from datetime import datetime, date

class DateTimeUtils:
	@staticmethod
	def is_valid_iso_string_date(value: str):
		try:
			date.fromisoformat(value)
		except:
			return False
		return True

	@staticmethod
	def is_valid_iso_string_datetime(value: str):
		try:
			datetime.fromisoformat(value)
		except:
			return False
		return True