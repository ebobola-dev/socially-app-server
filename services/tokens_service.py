import jwt
from datetime import datetime, timedelta, timezone

from config.jwt_config import JWT_CONFIG
from repositories.refresh_token_repository import RefreshTokenRepository
from sqlalchemy.ext.asyncio import AsyncSession
from models.role import Role


class TokensService:
    @staticmethod
    async def generate_pair_and_save_refresh(
        session: AsyncSession,
        user_id: str,
        device_id: str,
        user_role: Role,
    ):
        payload = {"id": str(user_id), "role": user_role.value}
        access_payload = payload.copy()
        refresh_payload = payload.copy()
        access_exp = datetime.now(timezone.utc) + timedelta(
            minutes=JWT_CONFIG.ACCESS_DURABILITY_MIN
        )
        refresh_exp = datetime.now(timezone.utc) + timedelta(
            days=JWT_CONFIG.REFRESH_DURABILITY_DAYS
        )
        access_payload["exp"] = access_exp
        refresh_payload["exp"] = refresh_exp
        access_token = jwt.encode(
            payload=access_payload,
            key=JWT_CONFIG.ACCESS_SERCER_KEY,
            algorithm=JWT_CONFIG.ENCODE_ALGORITNM,
        )
        refresh_token = jwt.encode(
            payload=refresh_payload,
            key=JWT_CONFIG.REFRESH_SERCER_KEY,
            algorithm=JWT_CONFIG.ENCODE_ALGORITNM,
        )
        await RefreshTokenRepository.create_or_update(
            session,
            user_id=user_id,
            device_id=device_id,
            value=refresh_token,
            exp_time=refresh_exp,
        )
        return access_token, refresh_token

    @staticmethod
    def decode_access(access_token: str):
        return jwt.decode(
            jwt=access_token,
            key=JWT_CONFIG.ACCESS_SERCER_KEY,
            algorithms=[JWT_CONFIG.ENCODE_ALGORITNM],
        )

    @staticmethod
    def decode_refresh(refresh_token: str):
        return jwt.decode(
            jwt=refresh_token,
            key=JWT_CONFIG.REFRESH_SERCER_KEY,
            algorithms=[JWT_CONFIG.ENCODE_ALGORITNM],
        )

    @staticmethod
    async def delete_refresh(
        session: AsyncSession,
        user_id,
        device_id,
    ):
        await RefreshTokenRepository.delete_one(session, user_id, device_id)

    @staticmethod
    async def get_refresh_by_user_and_device_ids(
        session: AsyncSession, user_id, device_id
    ):
        return await RefreshTokenRepository.get_one(session, user_id, device_id)

    @staticmethod
    async def clean_dead_refresh_tokens(session: AsyncSession):
        return await RefreshTokenRepository.delete_dead(session)
