from datetime import datetime, date
from zoneinfo import ZoneInfo


class DateTimeUtils:
    MOSCOW_ZONE = ZoneInfo("Europe/Moscow")

    @staticmethod
    def is_valid_iso_string_date(value: str):
        try:
            date.fromisoformat(value)
        except Exception as _:
            return False
        return True

    @staticmethod
    def is_valid_iso_string_datetime(value: str):
        try:
            datetime.fromisoformat(value)
        except Exception as _:
            return False
        return True
