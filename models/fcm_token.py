from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import CHAR, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel


class FCMToken(BaseModel):
    __tablename__ = "fcm_tokens"

    id: Mapped[str] = mapped_column(
        CHAR(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    device_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    value: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", back_populates="fcm_tokens")

    def __repr__(self):
        return f"<FCMToken>(uid: {self.user_id}, {self.value[:10]}...)"
