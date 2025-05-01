import colorlog
from logging import Logger

from config.logger_config import MY_LOGGER_CONFIG
from models.exceptions.initalize_exceptions import ConfigNotInitalizedButUsing


class MyLogger:
    @staticmethod
    def get_logger(name: str, level: str | int = MY_LOGGER_CONFIG.LEVEL) -> Logger:
        if not MY_LOGGER_CONFIG.INITALIZED:
            raise ConfigNotInitalizedButUsing("MY_LOGGER_CONFIG")
        logger = colorlog.getLogger(name)
        logger.addHandler(MY_LOGGER_CONFIG.COLOR_HANDLER)
        logger.propagate = False
        logger.setLevel(level)
        return logger
