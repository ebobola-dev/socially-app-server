from packaging.version import Version
from sqlalchemy.types import String, TypeDecorator


class VersionType(TypeDecorator):
    impl = String(10)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return str(value)

    def process_result_value(self, value, dialect):
        return Version(value)
