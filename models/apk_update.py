from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import CHAR, JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import BaseModel
from models.version_type import VersionType
from utils.sizes import SizeUtils


class ApkUpdate(BaseModel):
    __tablename__ = "apk_updates"

    id: Mapped[str] = mapped_column(
        CHAR(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        unique=True,
        nullable=False,
    )
    version: Mapped[VersionType] = mapped_column(
        VersionType, unique=True, nullable=False
    )
    descriptions: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    def __repr__(self):
        return f"<ApkUpdate>({self.version} ({SizeUtils.bytes_to_human_readable(self.file_size)}), uploaded_at: {self.uploaded_at})"

    def to_json(self, replace_descriptions: list[str] | None = None):
        result = super().to_json()
        if replace_descriptions:
            result["descriptions"] = replace_descriptions
        return result

    @property
    def file_key(self) -> str:
        return f'socially_app-v{self.version}.apk'