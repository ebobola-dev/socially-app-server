from random import randint
from datetime import datetime
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from config.server_config import SERVER_CONFIG
from models.apk_update import ApkUpdate
from models.version_type import VersionType
from models.exceptions.api_exceptions import *

class ApkUpdateRepository:
	@staticmethod
	async def get_by_version(session: AsyncSession, version: VersionType) -> ApkUpdate | None:
		query = select(ApkUpdate).where(ApkUpdate.version == version)
		result = await session.scalars(query)
		return result.first()

	@staticmethod
	async def create_new(session: AsyncSession, apk_update: ApkUpdate) -> ApkUpdate:
		session.add(apk_update)
		try:
			await session.flush()
			await session.refresh(apk_update)
			return apk_update
		except Exception as error:
			await session.rollback()
			raise DatabaseError(
				server_message=f'[ApkUpdateRepository | create_new] {error}'
			)

	@staticmethod
	async def get(session: AsyncSession, min_version: VersionType | None = None) -> list[ApkUpdate]:
		if min_version:
			query = select(ApkUpdate).where(ApkUpdate.version >= min_version).order_by(ApkUpdate.version.desc())
		else:
			query = select(ApkUpdate).order_by(ApkUpdate.version.desc())
		result = await session.scalars(query)
		return result.all()

	@staticmethod
	async def delete_by_version(session: AsyncSession, version: VersionType) -> int:
		result = await session.execute(
			delete(ApkUpdate)
			.where(ApkUpdate.version == version)
		)
		await session.flush()
		return result.rowcount