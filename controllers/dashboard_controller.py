from logging import Logger

from aiohttp.web import Request, json_response

from controllers.middlewares import authenticate, owner_role
from services.minio_service import MinioService


class DashboardController:
    def __init__(self, logger: Logger):
        self._logger = logger

    @authenticate()
    @owner_role()
    async def get_minio_stat(self, request: Request):
        stats = await MinioService.get_all_stats()
        json_stats = tuple(map(lambda stat: stat.to_json(), stats))
        return json_response(json_stats)