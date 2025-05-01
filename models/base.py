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

        json_view = {
            col.key: serialize_value(getattr(self, col.key))
            for col in self.__table__.columns
            if will_be_added(col.key)
        }

        if (
            not short
            and hasattr(self, "__relationship_fields__")
            and len(self.__relationship_fields__)
        ):
            for rel_field_key in self.__relationship_fields__:
                json_view[rel_field_key] = tuple(
                    obj.id for obj in getattr(self, rel_field_key)
                )

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


# * [Class Decorator] For relationship fields, will be serialized as list of obj.id (rel_field = [obj, obj, obj] -> [obj.id, obj.id, obj.id])
def relationship_fields(*field_names):
    def decorator(cls):
        cls.__relationship_fields__ = field_names
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
