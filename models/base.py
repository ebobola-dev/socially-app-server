from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase

from utils.serialize_util import serialize_value


class BaseModel(AsyncAttrs, DeclarativeBase):
    def to_json(self, safe=False, short=False) -> dict:
        def will_be_added(key) -> bool:
            if (
                short
                and hasattr(self, "__short_fields__")
                and key not in self.__short_fields__
            ):
                return False
            if (
                hasattr(self, "__protected_from_json_fields__")
                and key in self.__protected_from_json_fields__
            ):
                return False
            if (
                hasattr(self, "__safe_fields__")
                and key in self.__safe_fields__
                and not safe
            ):
                return False
            return True

        def ga(key):
            try:
                return serialize_value(getattr(self, key))
            except Exception as e:
                raise Exception(f"SERIALIZE ERROR ON KEY (short: {short}): {key}") from e

        json_view = {
            col.key: ga(col.key)
            for col in self.__table__.columns
            if will_be_added(col.key)
        }

        return json_view


# * [Class Decorator] For fields that will never be in JSON (e.g.: User.password, Otp.value)
def protected_from_json_fields(*field_names):
    def decorator(cls):
        cls.__protected_from_json_fields__ = field_names
        return cls

    return decorator


# * [Class Decorator] For fields that will be in JSON only when [safe = True] (When the user request himself) (e.g.: User.email_address)
def safe_fields(*field_names):
    def decorator(cls):
        cls.__safe_fields__ = field_names
        return cls

    return decorator


# * [Class Decorator] For fields that can't be updated
def allowed_to_update_fields(*field_names):
    def decorator(cls):
        cls.allowed_to_update_fields = field_names
        return cls

    return decorator


# * [Class Decorator] For fields that will be in JSON when [short = True]
def short_fields(*field_names):
    def decorator(cls):
        cls.__short_fields__ = field_names
        return cls

    return decorator
