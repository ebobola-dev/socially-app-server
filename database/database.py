from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from sqlalchemy import text, select

from config.database_config import DATABASE_CONFIG
from models.base import BaseModel
from models.exceptions.initalize_exceptions import ConfigNotInitalizedButUsing, UnableToInitializeService, DatabaseNotInitialized
from repositories.user_repository import UserRepositorty
class Database:
	engine: AsyncEngine
	session_maker: AsyncSession
	INITIALIZED: bool = False

	@staticmethod
	async def initialize():
		try:
			if not DATABASE_CONFIG.INITALIZED:
				raise ConfigNotInitalizedButUsing('DATABASE_CONFIG')
			Database.engine = await Database.check_database_exists()
			if await Database.is_database_empty():
				async with Database.engine.begin() as connection:
					await connection.run_sync(BaseModel.metadata.create_all)
			Database.session_maker = async_sessionmaker(Database.engine, expire_on_commit=False)
			Database.INITIALIZED = True
		except Exception as error:
			raise UnableToInitializeService('Database') from error

	@staticmethod
	async def dispose():
		await Database.engine.dispose()

	@staticmethod
	async def check_database_exists():
		engine_wo_db = create_async_engine(
			f'mysql+asyncmy://{DATABASE_CONFIG.USER}:{DATABASE_CONFIG.PASSWORD}@{DATABASE_CONFIG.HOST}:{DATABASE_CONFIG.PORT}/'
		)
		async with engine_wo_db.begin() as connection:
			await connection.execute(text(f'CREATE DATABASE IF NOT EXISTS {DATABASE_CONFIG.NAME}'))
			await connection.commit()
		await engine_wo_db.dispose()
		return create_async_engine(
			f'mysql+asyncmy://{DATABASE_CONFIG.USER}:{DATABASE_CONFIG.PASSWORD}@{DATABASE_CONFIG.HOST}:{DATABASE_CONFIG.PORT}/{DATABASE_CONFIG.NAME}',
			pool_pre_ping=True,
		)

	@staticmethod
	async def is_database_empty():
		try:
			async with Database.engine.connect() as connection:
				result = await connection.execute(select([text('SHOW TABLES')]))
				tables = await result.fetchall()
				return len(tables) == 0
		except:
			return True

	@staticmethod
	async def after_initialize():
		if not Database.INITIALIZED:
			raise DatabaseNotInitialized()
		async with Database.session_maker() as session:
			try:
				await UserRepositorty.reset_sids(session)
				await session.commit()
			except Exception as error:
				await session.rollback()
				raise