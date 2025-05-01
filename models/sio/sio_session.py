from models.role import Role


class SioSession:
    def __init__(self, sid: str):
        self._sid = sid

    @property
    def sid(self):
        return self._sid

    def authorize(
        self,
        user_id: str,
        user_role: Role,
        device_id: str,
    ):
        return AuthorizedSioSession(
            sid=self._sid,
            user_id=user_id,
            user_role=user_role,
            device_id=device_id,
        )


class AuthorizedSioSession(SioSession):
    def __init__(
        self,
        sid: str,
        user_id: str,
        user_role: Role,
        device_id: str,
    ):
        super().__init__(sid)
        self._user_id = user_id
        self._device_id = device_id
        if isinstance(user_role, int):
            self._user_role = Role(user_role)
        else:
            self._user_role = user_role

    @property
    def user_id(self):
        return self._user_id

    @property
    def user_role(self):
        return self._user_role

    @property
    def device_id(self):
        return self._device_id
