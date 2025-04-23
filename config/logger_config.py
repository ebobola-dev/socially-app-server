import colorlog
from os import getenv
from zoneinfo import ZoneInfo
from datetime import datetime

from config.server_config import SERVER_CONFIG
from models.exceptions.initalize_exceptions import UnableToInitializeService, ServerConfigNotInitialized

_MOSCOW_ZONE = ZoneInfo("Europe/Moscow")

class _MYFormatter(colorlog.ColoredFormatter):
	def formatTime(self, record, datefmt=None):
		dt = datetime.fromtimestamp(record.created, tz=_MOSCOW_ZONE)
		return dt.strftime(datefmt or "%Y-%m-%d %H:%M:%S %Z")

class MY_LOGGER_CONFIG:
	INITALIZED: bool = False
	LEVEL: str
	COLOR_HANDLER: colorlog.StreamHandler

	@staticmethod
	def initialize():
		try:
			if not SERVER_CONFIG.INITIALIZED:
				raise ServerConfigNotInitialized()
			MY_LOGGER_CONFIG.LEVEL = getenv('LOGGING_LEVEL')

			MY_LOGGER_CONFIG.COLOR_HANDLER = colorlog.StreamHandler()
			MY_LOGGER_CONFIG.COLOR_HANDLER.setFormatter(_MYFormatter(
				"%(log_color)s%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
				datefmt="%m.%d %H:%M:%S",
				log_colors={
					"DEBUG":    "purple",
					"INFO":     "cyan",
					"WARNING":  "yellow",
					"ERROR":    "red",
					"CRITICAL": "bold_red",
				},
			))
			MY_LOGGER_CONFIG.COLOR_HANDLER.setLevel(MY_LOGGER_CONFIG.LEVEL)

			MY_LOGGER_CONFIG.INITALIZED = True
		except Exception as error:
			raise UnableToInitializeService('MY_LOGGER_CONFIG') from error