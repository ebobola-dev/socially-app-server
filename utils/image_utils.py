import asyncio
import subprocess
import sys
from enum import Enum
from io import BytesIO
from pathlib import Path
from secrets import token_hex as random_string

from filetype import guess
from PIL import Image as pImage
from PIL import UnidentifiedImageError

from models.image_sizes import ImageSizes


class PillowValidatationResult(Enum):
    valid = 1
    unable = 2
    invalid = 3


class VerifyImageError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class ImageUtils:
    @staticmethod
    def is_valid_by_pillow(file_bytes: BytesIO) -> PillowValidatationResult:
        try:
            file_bytes.seek(0)
            img = pImage.open(file_bytes)
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
        except Exception:
            return False

    @staticmethod
    async def verify_image(source_buffer: BytesIO, source_extension: str) -> BytesIO:
        is_valid_by_filetype = ImageUtils.is_valid_by_filetype(source_buffer)
        if not is_valid_by_filetype:
            raise VerifyImageError("Invalid mimetype")
        source_buffer.seek(0)
        pillow_validation_result = ImageUtils.is_valid_by_pillow(source_buffer)
        match pillow_validation_result:
            case PillowValidatationResult.valid:
                return source_buffer
            case PillowValidatationResult.invalid:
                raise VerifyImageError("Invalid by Pillow")
        try:
            converted_bytes = await asyncio.to_thread(
                ImageUtils.magick_convert_sync,
                original_bytes=source_buffer.getvalue(),
                original_extension=source_extension,
            )
            return BytesIO(converted_bytes)
        except Exception as convert_error:
            raise VerifyImageError('Unable to convert by magick') from convert_error

    @staticmethod
    def split_image_sync(image_buffer: BytesIO) -> dict[ImageSizes, BytesIO]:
        original_image = pImage.open(image_buffer)
        original_image.load()
        result = {}
        image_buffer.seek(0)
        result[ImageSizes.s_original] = BytesIO(image_buffer.read())
        width, height = original_image.size
        for size in ImageSizes:
            if size == ImageSizes.s_original:
                continue
            target_size = size.value
            if max(width, height) <= target_size:
                continue
            if height > width:
                new_height = target_size
                new_width = int(width * (target_size / height))
            else:
                new_width = target_size
                new_height = int(height * (target_size / width))
            resized_image = original_image.resize(
                (new_width, new_height), pImage.Resampling.LANCZOS
            )
            img_buffer = BytesIO()
            save_format = original_image.format or "JPEG"
            resized_image.save(img_buffer, format=save_format)
            img_buffer.seek(0)
            result[size] = img_buffer
        return result

    @staticmethod
    def magick_convert_sync(original_bytes: bytes, original_extension: str) -> bytes:
        temp_dir_path = Path("temp/magick")
        temp_dir_path.mkdir(parents=True, exist_ok=True)
        temp_original_path = temp_dir_path / f"{random_string(8)}{original_extension}"
        temp_converted_path = temp_dir_path / f"{random_string(8)}{original_extension}"
        try:
            with open(temp_original_path, "wb") as converted_file:
                converted_file.write(original_bytes)
            cmd = "magick" if sys.platform == "win32" else "convert"
            subprocess.run(
                [cmd, str(temp_original_path) + "[0]", str(temp_converted_path)],
                check=True,
                capture_output=True,
            )
            with open(temp_converted_path, "rb") as converted_file:
                return converted_file.read()
        except Exception as error:
            raise RuntimeError(f"ImageMagick conversion failed: {error}") from error
        finally:
            temp_original_path.unlink(missing_ok=True)
            temp_converted_path.unlink(missing_ok=True)
