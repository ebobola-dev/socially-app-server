from os import getenv

from models.exceptions.initalize_exceptions import UnableToInitializeServiceError


class ServerConfig:
    INITIALIZED: bool = False
    HOST: str
    PORT: int
    OWNER_KEY: str
    BCRYPT_SALT_ROUNDS = 4
    ALLOWED_IMAGE_EXTENSIONS = (
        "jpg",
        "jpeg",
        "png",
        "webp",
    )
    MAX_IMAGE_SIZE = 7  # ? in MB
    OTP_CODE_DURABILITY_MIN = 15
    RUN_IN_DOCKER = False

    @staticmethod
    def initialize():
        try:
            ServerConfig.RUN_IN_DOCKER = bool(getenv("RUN_IN_DOCKER"))
            if not ServerConfig.RUN_IN_DOCKER:
                from dotenv import load_dotenv

                load_dotenv(override=True)
            ServerConfig.HOST = getenv("SERVER_HOST")
            ServerConfig.PORT = int(getenv("SERVER_PORT"))
            ServerConfig.OWNER_KEY = getenv("OWNER_KEY")
            ServerConfig.INITIALIZED = True
        except Exception as error:
            raise UnableToInitializeServiceError("SERVER_CONFIG") from error
