from os import getenv

from config.server_config import ServerConfig
from models.exceptions.initalize_exceptions import (
    ServerConfigNotInitializedError,
    UnableToInitializeServiceError,
)


class EmailConfig:
    INITALIZED: bool = False
    ADDRESS: str
    PASSWORD: str

    @staticmethod
    def initialize():
        try:
            if not ServerConfig.INITIALIZED:
                raise ServerConfigNotInitializedError()
            EmailConfig.ADDRESS = getenv("APP_EMAIL_ADDRESS")
            EmailConfig.PASSWORD = getenv("APP_EMAIL_PASSWORD")
            EmailConfig.INITALIZED = True
        except Exception as error:
            raise UnableToInitializeServiceError("EMAIL_CONFIG") from error
