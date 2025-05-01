from aiohttp.web import Request
from models.exceptions.api_exceptions import ValidationError


class Pagination:
    def __init__(self, page: int, per_page: int):
        self.page = page
        self.per_page = per_page

    @staticmethod
    def from_request(request: Request):
        try:
            page = int(request.query.get("page", 1))
            per_page = int(request.query.get("per_page", 10))
        except Exception as _:
            raise ValidationError("Invalid pagination data")
        if page < 1 or per_page < 1:
            raise ValidationError("Invalid pagination data")
        return Pagination(page=page, per_page=per_page)

    @staticmethod
    def default():
        return Pagination(
            page=1,
            per_page=10,
        )

    @property
    def offset(self):
        return (self.page - 1) * self.per_page
