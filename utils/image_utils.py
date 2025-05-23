from enum import Enum
from io import BytesIO

from filetype import guess
from PIL import Image, ImageOps, UnidentifiedImageError


class PillowValidatationResult(Enum):
    valid = 1
    unable = 2
    invalid = 3


class ImageSizes(Enum):
    s128 = "128"
    s512 = "512"
    original = "original"

    @classmethod
    def ordered(cls) -> list[str]:
        return ["128", "512", "original"]


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
        finally:
            file_bytes.seek(0)

    @staticmethod
    def is_valid_by_filetype(file_bytes: BytesIO) -> bool:
        try:
            file_bytes.seek(0)
            kind = guess(file_bytes.read(261))
            return kind is not None and kind.mime.startswith("image/")
        except Exception as error:
            print(f"error on filetype validation: {error}")
            return False

    @staticmethod
    def resize(original: BytesIO, size: int) -> BytesIO | None:
        source = BytesIO(original.getvalue())
        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image)
            if max(image.size) <= size:
                return None
            image.thumbnail((size, size), Image.Resampling.LANCZOS)

            resized = BytesIO()
            image.save(resized, format="JPEG", quality=85)
            resized.seek(0)
            return resized

    @staticmethod
    def split(original: BytesIO) -> dict[str, BytesIO]:
        original_copy = BytesIO(original.getvalue())
        result = {"original": original_copy}

        for size in [128, 512]:
            resized = ImageUtils.resize(original, size)
            if resized:
                result[str(size)] = resized

        return result

    @staticmethod
    def pick_best_available_size(size: str, available: list[str]):
        if size not in ImageSizes.__members__.values():
            return "original"
        ordered_sizes = ImageSizes.ordered()
        size_index = ordered_sizes.index(size)
        for s in reversed(ordered_sizes[: size_index + 1]):
            if s in available:
                return s
        return "original"
