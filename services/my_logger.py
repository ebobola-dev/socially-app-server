from logging import Logger

import colorlog

from config.logger_config import MyLoggerConfig
from models.exceptions.initalize_exceptions import ConfigNotInitalizedButUsingError


class MyLogger:
    @staticmethod
    def get_logger(name: str, level: str | int = MyLoggerConfig.LEVEL) -> Logger:
        if not MyLoggerConfig.INITALIZED:
            raise ConfigNotInitalizedButUsingError("MY_LOGGER_CONFIG")
        logger = colorlog.getLogger(name)
        logger.addHandler(MyLoggerConfig.COLOR_HANDLER)
        logger.propagate = False
        logger.setLevel(level)
        return logger
