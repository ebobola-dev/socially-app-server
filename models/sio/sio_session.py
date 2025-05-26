from models.role import Role


class SioSession:
    def __init__(
        self,
        sid: str,
        user_id: str,
        user_role: Role,
        device_id: str,
    ):
        self._sid = sid
        self._user_id = user_id
        self._device_id = device_id
        if isinstance(user_role, int):
            self._user_role = Role(user_role)
        else:
            self._user_role = user_role

    @property
    def sid(self):
        return self._sid

    @property
    def user_id(self):
        return self._user_id

    @property
    def user_role(self):
        return self._user_role

    @property
    def device_id(self):
        return self._device_id

    def __repr__(self):
        return f"<SioSession {self._sid}>(user_id: {self.user_id}, role: {self.user_role}, device_id: {self.device_id})"

    def to_json(self) -> dict:
        return {
            "sid": self._sid,
            "user_id": self._user_id,
            "user_role": self._user_role.value,
            "device_id": self._device_id,
        }

    @staticmethod
    def from_json(json_session: dict):
        return SioSession(
            sid=json_session.get("sid"),
            user_id=json_session.get("user_id"),
            user_role=Role(int(json_session.get("user_role"))),
            device_id=json_session.get("device_id"),
        )
