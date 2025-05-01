from os import getenv

from config.server_config import SERVER_CONFIG
from models.exceptions.initalize_exceptions import (
    UnableToInitializeService,
    ServerConfigNotInitialized,
)


class JWT_CONFIG:
    INITALIZED: bool = False
    ACCESS_SERCER_KEY: str
    REFRESH_SERCER_KEY: str
    ENCODE_ALGORITNM: str
    ACCESS_DURABILITY_MIN: int  #! in minutes
    REFRESH_DURABILITY_DAYS: int  #! in days

    @staticmethod
    def initialize():
        try:
            if not SERVER_CONFIG.INITIALIZED:
                raise ServerConfigNotInitialized()
            JWT_CONFIG.ACCESS_SERCER_KEY = getenv("JWT_ACCESS_SERCER_KEY")
            JWT_CONFIG.REFRESH_SERCER_KEY = getenv("JWT_REFRESH_SERCER_KEY")
            JWT_CONFIG.ENCODE_ALGORITNM = getenv("JWT_ENCODE_ALGORITNM")
            JWT_CONFIG.ACCESS_DURABILITY_MIN = int(getenv("JWT_ACCESS_DURABILITY_MIN"))
            JWT_CONFIG.REFRESH_DURABILITY_DAYS = int(
                getenv("JWT_REFRESH_DURABILITY_DAYS")
            )
            JWT_CONFIG.INITALIZED = True
        except Exception as error:
            raise UnableToInitializeService("JWT_CONFIG") from error
