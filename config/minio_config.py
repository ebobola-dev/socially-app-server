from os import getenv

from config.server_config import ServerConfig
from models.exceptions.initalize_exceptions import (
    ServerConfigNotInitializedError,
    UnableToInitializeServiceError,
)


class MinioConfig:
    INITALIZED: bool = False
    USER: str
    PASSWORD: str

    @staticmethod
    def initialize():
        try:
            if not ServerConfig.INITIALIZED:
                raise ServerConfigNotInitializedError()
            MinioConfig.USER = getenv("MINIO_ROOT_USER")
            MinioConfig.PASSWORD = getenv("MINIO_ROOT_PASSWORD")
            MinioConfig.INITALIZED = True
        except Exception as error:
            raise UnableToInitializeServiceError("MinioConfig") from error
