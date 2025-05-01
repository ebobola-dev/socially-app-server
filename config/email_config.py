from os import getenv

from config.server_config import SERVER_CONFIG
from models.exceptions.initalize_exceptions import (
    UnableToInitializeService,
    ServerConfigNotInitialized,
)


class EMAIL_CONFIG:
    INITALIZED: bool = False
    ADDRESS: str
    PASSWORD: str

    @staticmethod
    def initialize():
        try:
            if not SERVER_CONFIG.INITIALIZED:
                raise ServerConfigNotInitialized()
            EMAIL_CONFIG.ADDRESS = getenv("APP_EMAIL_ADDRESS")
            EMAIL_CONFIG.PASSWORD = getenv("APP_EMAIL_PASSWORD")
            EMAIL_CONFIG.INITALIZED = True
        except Exception as error:
            raise UnableToInitializeService("EMAIL_CONFIG") from error
