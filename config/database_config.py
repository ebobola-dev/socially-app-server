from os import getenv

from config.server_config import ServerConfig
from models.exceptions.initalize_exceptions import (
    ServerConfigNotInitializedError,
    UnableToInitializeServiceError,
)


class DatabaseConfig:
    INITALIZED: bool = False
    HOST: str
    PORT: str
    USER: str
    PASSWORD: str
    NAME: str

    @staticmethod
    def initialize():
        try:
            if not ServerConfig.INITIALIZED:
                raise ServerConfigNotInitializedError()
            DatabaseConfig.HOST = getenv("MYSQL_HOST")
            DatabaseConfig.PORT = getenv("MYSQL_PORT")
            DatabaseConfig.USER = getenv("MYSQL_USER")
            DatabaseConfig.PASSWORD = getenv("MYSQL_PASSWORD")
            DatabaseConfig.NAME = getenv("MYSQL_NAME")
            DatabaseConfig.INITALIZED = True
        except Exception as error:
            raise UnableToInitializeServiceError("DATABASE_CONFIG") from error
