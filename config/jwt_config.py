from os import getenv

from config.server_config import ServerConfig
from models.exceptions.initalize_exceptions import (
    ServerConfigNotInitializedError,
    UnableToInitializeServiceError,
)


class JwtConfig:
    INITALIZED: bool = False
    ACCESS_SERCER_KEY: str
    REFRESH_SERCER_KEY: str
    ENCODE_ALGORITNM: str
    ACCESS_DURABILITY_MIN: int  #! in minutes
    REFRESH_DURABILITY_DAYS: int  #! in days

    @staticmethod
    def initialize():
        try:
            if not ServerConfig.INITIALIZED:
                raise ServerConfigNotInitializedError()
            JwtConfig.ACCESS_SERCER_KEY = getenv("JWT_ACCESS_SERCER_KEY")
            JwtConfig.REFRESH_SERCER_KEY = getenv("JWT_REFRESH_SERCER_KEY")
            JwtConfig.ENCODE_ALGORITNM = getenv("JWT_ENCODE_ALGORITNM")
            JwtConfig.ACCESS_DURABILITY_MIN = int(getenv("JWT_ACCESS_DURABILITY_MIN"))
            JwtConfig.REFRESH_DURABILITY_DAYS = int(
                getenv("JWT_REFRESH_DURABILITY_DAYS")
            )
            JwtConfig.INITALIZED = True
        except Exception as error:
            raise UnableToInitializeServiceError("JWT_CONFIG") from error
