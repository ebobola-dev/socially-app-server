from datetime import datetime, timezone
from enum import Enum
from random import randint
from uuid import uuid4

from sqlalchemy import CHAR, JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import BaseModel, protected_from_json_fields
from utils.serialize_util import hide_email


@protected_from_json_fields("id", "value")
class Otp(BaseModel):
    __tablename__ = "otp"

    id: Mapped[CHAR] = mapped_column(
        CHAR(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        unique=True,
        nullable=False,
    )
    email_address: Mapped[String] = mapped_column(
        String(320), unique=True, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    value: Mapped[JSON] = mapped_column(
        JSON, nullable=False, default=lambda: list(randint(0, 9) for _ in range(4))
    )

    @staticmethod
    def new(email):
        return Otp(email_address=email)

    def __repr__(self):
        return f"<Otp>({self.email_address}, upd: {self.updated_at}, {self.value})"

    @property
    def can_update(self):
        delta = datetime.now() - self.updated_at
        return delta.seconds > 60

    @staticmethod
    def is_valid_value(otp_value) -> bool:
        if isinstance(otp_value, str):
            if len(otp_value) != 4:
                return False
            if not all(map(lambda c: c.isdigit(), otp_value)):
                return False
            return True
        if isinstance(otp_value, tuple | list):
            if len(otp_value) != 4:
                return False
            if any(map(lambda i: not isinstance(i, int), otp_value)):
                return False
            if any(map(lambda i: i < 0 or i > 9, otp_value)):
                return False
            return True
        return False

    def to_json(self, safe=False) -> dict:
        result = super().to_json(safe)
        if not safe:
            result["email_address"] = hide_email(self.email_address)
        return result


class OtpDestiny(Enum):
    registration = "registration"
    reset_password = "reset password"
