from enum import Enum

from aiohttp.web import Request


class ImageSizes(Enum):
    s_256 = 256         #% for small avatars
    s_512 = 512         #% for ~1/3 mobile screen
    s_1024 = 1024       #% for full [width] of mobile screen
    s_original = 4

    @property
    def str_view(self):
        return {
            ImageSizes.s_256: "256",
            ImageSizes.s_512: "512",
            ImageSizes.s_1024: "1024",
            ImageSizes.s_original: "original",
        }[self]

    @classmethod
    def from_request(cls, request: Request) -> "ImageSizes":
        str_size = request.query.get("size", "")
        match str_size:
            case "256":
                return cls.s_256
            case "512":
                return cls.s_512
            case "1024":
                return cls.s_1024
            case _:
                return cls.s_original

    @classmethod
    def all_sizes_ordered(cls):
        return [cls.s_256, cls.s_512, cls.s_1024, cls.s_original]

    @classmethod
    def get_next_available_size(cls, requested: "ImageSizes") -> list["ImageSizes"]:
        all_sizes = cls.all_sizes_ordered()
        index = all_sizes.index(requested)
        return all_sizes[index:]
