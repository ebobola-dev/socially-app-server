from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.exceptions.api_exceptions import DatabaseError
from models.refresh_token import RefreshToken


class RefreshTokenRepository:
    @staticmethod
    async def get_all_by_user_id(
        session: AsyncSession, user_id: str
    ) -> list[RefreshToken]:
        query = select(RefreshToken).where(RefreshToken.user_id == user_id)
        result = await session.scalars(query)
        return result.all()

    @staticmethod
    async def get_one(
        session: AsyncSession, user_id: str, device_id: str
    ) -> RefreshToken | None:
        query = select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.device_id == device_id
        )
        result = await session.scalars(query)
        return result.first()

    @staticmethod
    async def create_or_update(
        session: AsyncSession,
        user_id: str,
        device_id: str,
        value: str,
        exp_time: datetime,
    ) -> RefreshToken:
        query = select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.device_id == device_id
        )
        result = await session.scalars(query)
        refresh_token: RefreshToken | None = result.first()
        if refresh_token:
            refresh_token.value = value
            refresh_token.exp_time = exp_time
        else:
            refresh_token = RefreshToken(
                user_id=user_id,
                device_id=device_id,
                value=value,
                exp_time=exp_time,
            )
            session.add(refresh_token)
        try:
            await session.flush()
            await session.refresh(refresh_token)
            return refresh_token
        except Exception as error:
            await session.rollback()
            raise DatabaseError(
                server_message=f"[RefreshToken | create_or_update] {error}"
            )

    @staticmethod
    async def delete_one(session: AsyncSession, user_id: str, device_id: str) -> None:
        try:
            await session.execute(
                delete(RefreshToken).where(
                    RefreshToken.user_id == user_id, RefreshToken.device_id == device_id
                )
            )
            await session.flush()
        except Exception as error:
            await session.rollback()
            raise DatabaseError(server_message=f"[RefreshToken | delete_one] {error}")

    @staticmethod
    async def delete_all_by_user_id(
        session: AsyncSession,
        user_id: str,
    ):
        try:
            await session.execute(
                delete(RefreshToken).where(RefreshToken.user_id == user_id)
            )
            await session.flush()
        except Exception as error:
            await session.rollback()
            raise DatabaseError(
                server_message=f"[RefreshToken | delete_all_by_user_id] {error}"
            )

    @staticmethod
    async def delete_dead(
        session: AsyncSession,
    ) -> int:
        try:
            result = await session.execute(
                delete(RefreshToken).where(RefreshToken.exp_time < datetime.now())
            )
            await session.flush()
            return result.rowcount
        except Exception as error:
            await session.rollback()
            raise DatabaseError(server_message=f"[RefreshToken | delete_dead] {error}")
