from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
	AsyncEngine,
	AsyncSession,
	async_sessionmaker,
	create_async_engine,
)

from config.database_config import DatabaseConfig
from models.exceptions.initalize_exceptions import (
	ConfigNotInitalizedButUsingError,
	DatabaseNotInitializedError,
	UnableToInitializeServiceError,
)
from repositories.user_repository import UserRepository


class Database:
	engine: AsyncEngine
	session_maker: AsyncSession
	INITIALIZED: bool = False

	@staticmethod
	async def initialize():
		try:
			if not DatabaseConfig.INITALIZED:
				raise ConfigNotInitalizedButUsingError('DATABASE_CONFIG')
			Database.engine = await Database.check_database_exists()
			# if await Database.is_database_empty():
			# 	async with Database.engine.begin() as connection:
			# 		await connection.run_sync(BaseModel.metadata.create_all)
			Database.session_maker = async_sessionmaker(Database.engine, expire_on_commit=False)
			Database.INITIALIZED = True
		except Exception as error:
			raise UnableToInitializeServiceError('Database') from error

	@staticmethod
	async def dispose():
		await Database.engine.dispose()

	@staticmethod
	async def check_database_exists():
		engine_wo_db = create_async_engine(
			f'mysql+asyncmy://{DatabaseConfig.USER}:{DatabaseConfig.PASSWORD}@{DatabaseConfig.HOST}:{DatabaseConfig.PORT}/'
		)
		async with engine_wo_db.begin() as connection:
			await connection.execute(text(f'CREATE DATABASE IF NOT EXISTS {DatabaseConfig.NAME}'))
			await connection.commit()
		await engine_wo_db.dispose()
		return create_async_engine(
			f'mysql+asyncmy://{DatabaseConfig.USER}:{DatabaseConfig.PASSWORD}@{DatabaseConfig.HOST}:{DatabaseConfig.PORT}/{DatabaseConfig.NAME}',
			pool_pre_ping=True,
		)

	@staticmethod
	async def is_database_empty():
		try:
			async with Database.engine.connect() as connection:
				result = await connection.execute(select([text('SHOW TABLES')]))
				tables = await result.fetchall()
				return len(tables) == 0
		except Exception as _:
			return True

	@staticmethod
	async def after_initialize():
		if not Database.INITIALIZED:
			raise DatabaseNotInitializedError()
		async with Database.session_maker() as session:
			try:
				await UserRepository.reset_sids(session)
				await session.commit()
			except Exception as _:
				await session.rollback()
				raise