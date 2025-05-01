from enum import Enum
from io import BytesIO

from filetype import guess
from PIL import Image, UnidentifiedImageError


class PillowValidatationResult(Enum):
    valid = 1
    unable = 2
    invalid = 3


class ImageUtils:
    @staticmethod
    def is_valid_by_pillow(file_bytes: BytesIO) -> PillowValidatationResult:
        try:
            file_bytes.seek(0)
            img = Image.open(file_bytes)
            img.verify()
            return PillowValidatationResult.valid
        except UnidentifiedImageError as _:
            return PillowValidatationResult.unable
        except Exception:
            return PillowValidatationResult.invalid

    @staticmethod
    def is_valid_by_filetype(file_bytes: BytesIO) -> bool:
        try:
            file_bytes.seek(0)
            kind = guess(file_bytes.read(261))
            return kind is not None and kind.mime.startswith("image/")
        except Exception as error:
            print(f"error on filetype validation: {error}")
            return False
