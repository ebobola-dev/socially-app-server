from datetime import datetime, timezone

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import FCMToken


class FCMTokenRepository:
    @staticmethod
    async def get_all_by_user(
        session: AsyncSession,
        user_id: str,
        device_id: str | None = None,
    ) -> list[FCMToken]:
        query = select(FCMToken).where(FCMToken.user_id == user_id)
        if device_id:
            query = query.where(FCMToken.device_id == device_id)
        result = await session.scalars(query)
        return result.all()

    @staticmethod
    async def create_or_update(
        session: AsyncSession, user_id: str, device_id: str, new_value: str
    ) -> FCMToken:
        query = select(FCMToken).where(
            and_(FCMToken.user_id == user_id, FCMToken.device_id == device_id)
        )
        result = await session.scalars(query)
        token = result.first()
        if token:
            token.value = new_value
            token.updated_at = datetime.now(timezone.utc)
        else:
            token = FCMToken(
                user_id=user_id,
                device_id=device_id,
                value=new_value,
            )
            session.add(token)
        await session.flush()
        await session.refresh(token)
        return token

    @staticmethod
    async def delete_by_user(
        session: AsyncSession, user_id: str, device_id: str | None = None
    ) -> int:
        query = delete(FCMToken).where(FCMToken.user_id == user_id)
        if device_id:
            query = query.where(FCMToken.device_id == device_id)
        result = await session.execute(query)
        await session.flush()
        return result.rowcount

    @staticmethod
    async def delete_by_id(session: AsyncSession, token_id: str):
        query = delete(FCMToken).where(FCMToken.id == token_id)
        result = await session.execute(query)
        await session.flush()
        return result.rowcount