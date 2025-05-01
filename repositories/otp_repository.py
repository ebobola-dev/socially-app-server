from random import randint
from datetime import datetime
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from config.server_config import SERVER_CONFIG
from models.otp import Otp
from models.exceptions.api_exceptions import (
    DatabaseError,
    CouldNotFoundOtpWithEmail,
    OtpCodeIsOutdated,
    IncorrectOtpCode,
)


class OtpRepository:
    @staticmethod
    async def get_by_email(session: AsyncSession, email: str) -> Otp | None:
        query = select(Otp).where(Otp.email_address == email)
        result = await session.scalars(query)
        return result.first()

    @staticmethod
    async def can_update(session: AsyncSession, email: str) -> bool:
        query = select(Otp).where(Otp.email_address == email)
        result = await session.scalars(query)
        otp: Otp | None = result.first()
        if not otp:
            return True
        return otp.can_update

    @staticmethod
    async def create_or_update(session: AsyncSession, email: str) -> Otp:
        query = select(Otp).where(Otp.email_address == email)
        result = await session.scalars(query)
        otp: Otp | None = result.first()
        if otp:
            otp.value = list(randint(0, 9) for _ in range(4))
        else:
            otp = Otp.new(email)
            session.add(otp)
        try:
            await session.flush()
            await session.refresh(otp)
            return otp
        except Exception as error:
            await session.rollback()
            raise DatabaseError(server_message=f"[Otp | create_or_update] {error}")

    @staticmethod
    async def delete_dead(session: AsyncSession, dead_time: datetime) -> int:
        result = await session.execute(delete(Otp).where(Otp.updated_at < dead_time))
        await session.flush()
        return result.rowcount

    @staticmethod
    async def verify(session: AsyncSession, email: str, otp_code: list[int]) -> None:
        saved_otp = await OtpRepository.get_by_email(session, email)
        if saved_otp is None:
            raise CouldNotFoundOtpWithEmail(email)
        timedelta = datetime.now() - saved_otp.updated_at
        difference_in_minutes = (timedelta.seconds // 60) % 60
        if difference_in_minutes > SERVER_CONFIG.OTP_CODE_DURABILITY_MIN:
            raise OtpCodeIsOutdated()
        if saved_otp.value != otp_code:
            raise IncorrectOtpCode()
