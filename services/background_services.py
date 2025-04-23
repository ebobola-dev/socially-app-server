import asyncio
from aiohttp.web import Application
from datetime import datetime, timedelta, timezone

from repositories.otp_repository import OtpRepository
from services.tokens_service import TokensService
from services.my_logger import MyLogger
from database.database import Database
from utils.datetime_utils import DateTimeUtils

class BackgroundServices:
	CLEANING_OTP_SECONDS_DELAY = 60 * 60 * 6 #? EVERY 6 HOURS
	CLEANING_REFRESH_TOKEN_SECONDS_DELAY = 60 * 60 * 24 #? EVERY 24 HOURS

	@staticmethod
	async def start_background_tasks(app: Application):
		app['cleaning_otp_database'] = asyncio.create_task(BackgroundServices.cleaning_otp_database())
		app['cleaning_refresh_token_database'] = asyncio.create_task(BackgroundServices.cleaning_refresh_token_database())

	@staticmethod
	async def cleanup_background_tasks(app: Application):
		cleaning_otp_task: asyncio.Task = app['cleaning_otp_database']
		cleaning_refresh_token_task: asyncio.Task = app['cleaning_refresh_token_database']
		cleaning_otp_task.cancel()
		cleaning_refresh_token_task.cancel()

	@staticmethod
	async def cleaning_otp_database():
		logger = MyLogger.get_logger('Background Service')
		delay = BackgroundServices.CLEANING_OTP_SECONDS_DELAY
		while True:
			dead_date = datetime.now() - timedelta(hours=1)
			async with Database.session_maker() as session:
				try:
					deleted_count = await OtpRepository.delete_dead(session, dead_date)
					await session.commit()
					logger.info(f'Deleted {deleted_count} OTP codes')
				except Exception as error:
					await session.rollback()
					logger.error(f'Error on cleaing OTP codes: {error}')
				finally:
					again_start_time = (datetime.now(timezone.utc).astimezone(DateTimeUtils.MOSCOW_ZONE) + timedelta(seconds=delay)).strftime('%H:%M:%S')
					logger.info(f'OTP cleaning will be started again at {again_start_time}\n')
					try:
						await asyncio.sleep(delay)
					except asyncio.CancelledError:
						logger.warning(f'OTP cleaning task was cancelled')
						break

	@staticmethod
	async def cleaning_refresh_token_database():
		logger = MyLogger.get_logger('Background Service')
		delay = BackgroundServices.CLEANING_REFRESH_TOKEN_SECONDS_DELAY
		while True:
			async with Database.session_maker() as session:
				try:
					deleted_count = await TokensService.clean_dead_refresh_tokens(session)
					await session.commit()
					logger.info(f'Deleted {deleted_count} refresh tokens')
				except Exception as error:
					await session.rollback()
					logger.error(f'Error on cleaing refresh tokens: {error}')
				finally:
					again_start_time = (datetime.now(timezone.utc).astimezone(DateTimeUtils.MOSCOW_ZONE) + timedelta(seconds=delay)).strftime('%d.%m %H:%M:%S')
					logger.info(f'Refresh token cleaning will be started again on {again_start_time}\n')
					try:
						await asyncio.sleep(delay)
					except asyncio.CancelledError:
						logger.warning(f'Refresh token cleaning task was cancelled')
						break