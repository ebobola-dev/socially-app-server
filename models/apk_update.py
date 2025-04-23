from uuid import uuid4
from sqlalchemy import CHAR, DateTime, String, Integer
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone

from utils.sizes import SizeUtils
from models.base import *
from models.version_type import VersionType

class ApkUpdate(BaseModel):
	__tablename__ = 'apk_updates'

	id: Mapped[CHAR] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid4()), unique=True, nullable=False)
	version: Mapped[VersionType] = mapped_column(VersionType, unique=True, nullable=False)
	description: Mapped[String] = mapped_column(String(512), nullable=False)
	uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
	file_size: Mapped[int] = mapped_column(Integer, nullable=False)

	def __repr__(self):
		return f'<ApkUpdate>({self.version} ({SizeUtils.bytes_to_human_readable(self.file_size)}), uploaded_at: {self.uploaded_at})'

	def to_json(self, replace_descriptions: list[str] | None = None):
		result = super().to_json()
		result.pop('description', None)
		if replace_descriptions:
			result['descriptions'] = replace_descriptions
		else:
			result['descriptions'] = [self.description, ]
		return result