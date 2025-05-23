from aiohttp.web import Request

from models.exceptions.api_exceptions import BadRequestError


class Pagination:
    def __init__(self, offset: int, limit: int):
        self.offset = offset
        self.limit = limit

    @staticmethod
    def from_request(request: Request):
        try:
            offset = int(request.query.get("offset", 0))
            limit = int(request.query.get("limit", 10))
        except Exception as _:
            raise BadRequestError("Invalid pagination data")
        if offset < 0 or limit < 0:
            raise BadRequestError("Invalid pagination data")
        return Pagination(offset=offset, limit=limit)

    @staticmethod
    def default():
        return Pagination(
            offset=0,
            limit=10,
        )

    def __str__(self):
        return f"<Pagination>(offset: {self.offset}, limit: {self.limit})"
