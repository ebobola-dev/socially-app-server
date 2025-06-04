from enum import Enum

from aiohttp.web import Request


class ImageSizes(Enum):
    s_128 = 128
    s_512 = 512
    s_original = 3

    @property
    def str_view(self):
        return {
            ImageSizes.s_128: "128",
            ImageSizes.s_512: "512",
            ImageSizes.s_original: "original",
        }[self]

    @classmethod
    def from_request(cls, request: Request) -> "ImageSizes":
        str_size = request.query.get("size", "")
        match str_size:
            case "128":
                return cls.s_128
            case "512":
                return cls.s_512
            case _:
                return cls.s_original

    @classmethod
    def all_sizes_ordered(cls):
        return [cls.s_128, cls.s_512, cls.s_original]

    @classmethod
    def get_next_available_size(cls, requested: "ImageSizes") -> list["ImageSizes"]:
        all_sizes = cls.all_sizes_ordered()
        index = all_sizes.index(requested)
        return all_sizes[index:]
