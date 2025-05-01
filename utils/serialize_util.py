from datetime import date, datetime, timezone
from enum import Enum

from packaging.version import Version


def serialize_value(value):
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Version):
        return str(value)
    return value


def hide_email(email: str) -> str:
    if len(email) < 4:
        return email
    if "@" not in email:
        return email
    result = ""
    local_part, domian = email.split("@", maxsplit=1)
    result += local_part[0] + "*" * (len(local_part) - 1)
    result += "@"
    sub_domian, top_level_domian = domian.rsplit(".", maxsplit=1)
    result += "*" * len(sub_domian)
    result += "*" * (len(top_level_domian) - 1) + top_level_domian[-2:]
    return result
