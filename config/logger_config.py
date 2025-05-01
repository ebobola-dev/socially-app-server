from datetime import datetime
from os import getenv

import colorlog
from zoneinfo import ZoneInfo

from config.server_config import ServerConfig
from models.exceptions.initalize_exceptions import (
    ServerConfigNotInitializedError,
    UnableToInitializeServiceError,
)

_MOSCOW_ZONE = ZoneInfo("Europe/Moscow")


class _MYFormatter(colorlog.ColoredFormatter):
    def formatTime(self, record, datefmt=None):  # noqa: N802
        dt = datetime.fromtimestamp(record.created, tz=_MOSCOW_ZONE)
        return dt.strftime(datefmt or "%Y-%m-%d %H:%M:%S %Z")


class MyLoggerConfig:
    INITALIZED: bool = False
    LEVEL: str
    COLOR_HANDLER: colorlog.StreamHandler

    @staticmethod
    def initialize():
        try:
            if not ServerConfig.INITIALIZED:
                raise ServerConfigNotInitializedError()
            MyLoggerConfig.LEVEL = getenv("LOGGING_LEVEL")

            MyLoggerConfig.COLOR_HANDLER = colorlog.StreamHandler()
            MyLoggerConfig.COLOR_HANDLER.setFormatter(
                _MYFormatter(
                    "%(log_color)s%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
                    datefmt="%d.%m %H:%M:%S",
                    log_colors={
                        "DEBUG": "purple",
                        "INFO": "cyan",
                        "WARNING": "yellow",
                        "ERROR": "red",
                        "CRITICAL": "bold_red",
                    },
                )
            )
            MyLoggerConfig.COLOR_HANDLER.setLevel(MyLoggerConfig.LEVEL)

            MyLoggerConfig.INITALIZED = True
        except Exception as error:
            raise UnableToInitializeServiceError("MY_LOGGER_CONFIG") from error
