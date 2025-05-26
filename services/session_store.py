import json
from functools import wraps

from redis.asyncio import Redis

from models.exceptions.initalize_exceptions import (
    ServiceNotInitalizedButUsingError,
    UnableToInitializeServiceError,
)
from models.sio.sio_session import SioSession


def check_initialized(handler):
    @wraps(handler)
    async def wrapper(cls, *args, **kwargs):
        if not cls.INITALIZED:
            raise ServiceNotInitalizedButUsingError("SessionStore(redis)")
        return await handler(cls, *args, **kwargs)

    return wrapper


class SessionStore:
    INITALIZED: bool = False
    redis: Redis

    @classmethod
    async def initialize(cls, clear_data: bool = True):
        try:
            cls.redis = Redis(host="redis", port=6379, decode_responses=True)
            if clear_data:
                await cls.redis.flushall()
            cls.INITALIZED = True
        except Exception as error:
            raise UnableToInitializeServiceError("SessionStore(redis)") from error

    @classmethod
    @check_initialized
    async def get_all_keys(cls):
        return await cls.redis.scan()

    @classmethod
    @check_initialized
    async def save_session(cls, session: SioSession):
        sid = session.sid
        user_id = session.user_id
        json_session = session.to_json()
        await cls.redis.set(f"sid:{sid}", json.dumps(json_session))
        await cls.redis.sadd(f"user_sid:{user_id}", sid)

    @classmethod
    @check_initialized
    async def get_session_by_sid(cls, sid: str) -> SioSession | None:
        data = await cls.redis.get(f"sid:{sid}")
        return SioSession.from_json(json.loads(data)) if data else None

    @classmethod
    @check_initialized
    async def get_sids_by_user_id(cls, user_id: str) -> set:
        return await cls.redis.smembers(f"user_sid:{user_id}")

    @classmethod
    @check_initialized
    async def remove_session(cls, sid: str):
        session = await cls.get_session_by_sid(sid)
        if session:
            user_id = session.user_id
            await cls.redis.srem(f"user_sid:{user_id}", sid)
        await cls.redis.delete(f"sid:{sid}")
