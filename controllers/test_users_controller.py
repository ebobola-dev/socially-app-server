from logging import Logger
from aiohttp.web import Request, Response

from controllers.sio_controller import SioController


class TestUsersController:
    def __init__(self, logger: Logger, main_sio_namespace: SioController):
        self._logger = logger
        self._sio = main_sio_namespace

    async def test_owner_role(self, request: Request):
        return Response(text=f"You role is {request.user_role.name}")

    async def test_admin_role(self, request: Request):
        return Response(text=f"You role is {request.user_role.name}")
