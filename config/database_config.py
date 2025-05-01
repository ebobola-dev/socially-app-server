from os import getenv

from config.server_config import SERVER_CONFIG
from models.exceptions.initalize_exceptions import (
    UnableToInitializeService,
    ServerConfigNotInitialized,
)


class DATABASE_CONFIG:
    INITALIZED: bool = False
    HOST: str
    PORT: str
    USER: str
    PASSWORD: str
    NAME: str

    @staticmethod
    def initialize():
        try:
            if not SERVER_CONFIG.INITIALIZED:
                raise ServerConfigNotInitialized()
            DATABASE_CONFIG.HOST = getenv("MYSQL_HOST")
            DATABASE_CONFIG.PORT = getenv("MYSQL_PORT")
            DATABASE_CONFIG.USER = getenv("MYSQL_USER")
            DATABASE_CONFIG.PASSWORD = getenv("MYSQL_PASSWORD")
            DATABASE_CONFIG.NAME = getenv("MYSQL_NAME")
            DATABASE_CONFIG.INITALIZED = True
        except Exception as error:
            raise UnableToInitializeService("DATABASE_CONFIG") from error
