from datetime import date, datetime, timezone

import bcrypt
from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config.server_config import ServerConfig
from models.avatar_type import AvatarType
from models.exceptions.api_exceptions import (
    AlreadyFollowingError,
    CantFollowUnlollowYouselfError,
    CouldNotFoundUserWithIdError,
    DatabaseError,
    NotFollowingAnywayError,
    NothingToUpdateError,
    OwnerAlreadyRegisteredError,
    UserWithEmailHasAlreadyCompletedRegistrationError,
)
from models.gender import Gender
from models.pagination import Pagination
from models.role import Role
from models.user import User
from models.user_subscriptions import user_subscriptions


class UserRepositorty:
    @staticmethod
    async def get_by_id(session: AsyncSession, user_id: str) -> User | None:
        query = (
            select(User)
            .where(User.id == user_id)
            .options(
                selectinload(User.following),
                selectinload(User.followers),
            )
        )
        result = await session.scalars(query)
        return result.first()

    @staticmethod
    async def get_by_email(session: AsyncSession, email: str) -> User | None:
        query = (
            select(User)
            .where(User.email_address == email)
            .options(
                selectinload(User.following),
                selectinload(User.followers),
            )
        )
        result = await session.scalars(query)
        return result.first()

    @staticmethod
    async def get_by_username(session: AsyncSession, username: str) -> User | None:
        query = (
            select(User)
            .where(User.username == username)
            .options(
                selectinload(User.following),
                selectinload(User.followers),
            )
        )
        result = await session.scalars(query)
        return result.first()

    @staticmethod
    async def create_new(
        session: AsyncSession, email: str, role: Role = Role.user
    ) -> User:
        if role == Role.owner:
            existing_owner = await UserRepositorty.get_owner(session)
            if existing_owner:
                raise OwnerAlreadyRegisteredError()
        new_user = User.new(email, role)
        session.add(new_user)
        try:
            await session.flush()
            await session.refresh(new_user)
            return new_user
        except Exception as error:
            await session.rollback()
            raise DatabaseError(server_message=f"[User | create_new] {error}")

    @staticmethod
    async def delete(session: AsyncSession, user_id: str) -> None:
        user = await session.get(User, user_id)
        if user:
            await session.delete(user)
            await session.flush()

    @staticmethod
    async def get_owner(
        session: AsyncSession,
    ) -> User | None:
        query = (
            select(User)
            .where(User.role == Role.owner)
            .options(
                selectinload(User.following),
                selectinload(User.followers),
            )
        )
        result = await session.scalars(query)
        return result.first()

    @staticmethod
    async def get_all(
        session: AsyncSession,
        pagination=Pagination.default(),
        ignore_id: str = "",
        ignore_incomplete_registration=True,
    ) -> list[User]:
        query = (
            select(User)
            .where(
                and_(
                    User.id != ignore_id,
                    User.is_registration_completed
                    if ignore_incomplete_registration
                    else True,
                ),
            )
            .options(
                selectinload(User.following),
                selectinload(User.followers),
            )
            .offset(pagination.offset)
            .limit(pagination.per_page)
        )
        result = await session.scalars(query)
        return result.all()

    @staticmethod
    async def find_by_pattern(
        session: AsyncSession,
        pattern: str,
        pagination: Pagination = Pagination.default(),
        ignore_id: str = "",
    ) -> list[User]:
        query = (
            select(User)
            .where(
                and_(
                    or_(
                        User.username.ilike(f"%{pattern}%"),
                        User.fullname.ilike(f"%{pattern}%"),
                    ),
                    User.id != ignore_id,
                    User.is_registration_completed,
                ),
            )
            .options(
                selectinload(User.following),
                selectinload(User.followers),
            )
            .offset(pagination.offset)
            .limit(pagination.per_page)
        )
        result = await session.scalars(query)
        return result.all()

    @staticmethod
    async def update_password(
        session: AsyncSession, user_id: str, new_password: str
    ) -> User:
        user: User | None = await session.get(User, user_id)
        if user is None:
            raise CouldNotFoundUserWithIdError(user_id)
        user.hashed_password = bcrypt.hashpw(
            new_password.encode(),
            salt=bcrypt.gensalt(rounds=ServerConfig.BCRYPT_SALT_ROUNDS),
        )
        try:
            await session.flush()
            await session.refresh(user)
            return user
        except Exception as error:
            await session.rollback()
            raise DatabaseError(server_message=f"[User | update_password] {error}")

    @staticmethod
    async def follow(session: AsyncSession, subscriber_id: str, target_id: str) -> User:
        if subscriber_id == target_id:
            raise CantFollowUnlollowYouselfError()
        subscriber = await session.get(User, subscriber_id)
        target = await session.get(User, target_id)
        if not subscriber:
            raise CouldNotFoundUserWithIdError(subscriber_id)
        if not target:
            raise CouldNotFoundUserWithIdError(target_id)
        if target in await subscriber.awaitable_attrs.following:
            raise AlreadyFollowingError(
                sub_username=subscriber.username,
                target_username=target.username,
            )
        subscriber.following.append(target)
        try:
            await session.flush()
            await session.refresh(subscriber)
            return subscriber
        except Exception as error:
            await session.rollback()
            raise DatabaseError(server_message=f"[User | follow] {error}")

    @staticmethod
    async def unfollow(
        session: AsyncSession, subscriber_id: str, target_id: str
    ) -> User:
        if subscriber_id == target_id:
            raise CantFollowUnlollowYouselfError()
        subscriber = await session.get(User, subscriber_id)
        target = await session.get(User, target_id)
        if not subscriber:
            raise CouldNotFoundUserWithIdError(subscriber_id)
        if not target:
            raise CouldNotFoundUserWithIdError(target_id)
        if target not in await subscriber.awaitable_attrs.following:
            raise NotFollowingAnywayError(
                sub_username=subscriber.username,
                target_username=target.username,
            )
        subscriber.following.remove(target)
        try:
            await session.flush()
            await session.refresh(subscriber)
            return subscriber
        except Exception as error:
            await session.rollback()
            raise DatabaseError(server_message=f"[User | unfollow] {error}")

    @staticmethod
    async def complete_registration(
        session: AsyncSession,
        user_id: str,
        date_of_birth: date,
        username: str,
        password: str,
        fullname: str = "",
        gender: Gender | None = None,
        about_me: str = "",
    ) -> User:
        if fullname is None:
            fullname = ""
        if about_me is None:
            about_me = ""
        user: User = await session.get(User, user_id)
        if not user:
            raise CouldNotFoundUserWithIdError(user_id)
        if user.is_registration_completed:
            raise UserWithEmailHasAlreadyCompletedRegistrationError(user.email_address)
        user.username = username
        user.hashed_password = bcrypt.hashpw(
            password.encode(),
            salt=bcrypt.gensalt(rounds=ServerConfig.BCRYPT_SALT_ROUNDS),
        )
        user.fullname = fullname
        user.date_of_birth = date_of_birth
        user.gender = gender
        user.about_me = about_me
        user.is_registration_completed = True
        try:
            await session.flush()
            await session.refresh(user)
            return user
        except Exception as error:
            await session.rollback()
            raise DatabaseError(
                server_message=f"[User | complete_registration] {error}"
            )

    @staticmethod
    async def update_avatar(
        session: AsyncSession,
        user_id: str,
        new_avatar_type: AvatarType,
        new_avatar_id: str | None = None,
    ) -> User:
        user: User = await session.get(User, user_id)
        if not user:
            raise CouldNotFoundUserWithIdError(user_id)
        user.avatar_type = new_avatar_type
        user.avatar_id = new_avatar_id
        try:
            await session.flush()
            await session.refresh(user)
            return user
        except Exception as error:
            await session.rollback()
            raise DatabaseError(server_message=f"[User | update_avatar] {error}")

    @staticmethod
    async def delete_avatar(session: AsyncSession, user_id: str) -> User:
        user: User = await session.get(User, user_id)
        if not user:
            raise CouldNotFoundUserWithIdError(user_id)
        user.avatar_type = None
        user.avatar_id = None
        try:
            await session.flush()
            await session.refresh(user)
            return user
        except Exception as error:
            await session.rollback()
            raise DatabaseError(server_message=f"[User | delete_avatar] {error}")

    @staticmethod
    async def toggle_online(
        session: AsyncSession, user_id: str, new_is_online_value: bool
    ) -> User:
        user: User = await session.get(User, user_id)
        if not user:
            raise CouldNotFoundUserWithIdError(user_id)
        if user.is_online and not new_is_online_value:
            user.last_seen = datetime.now(timezone.utc)
        user.is_online = new_is_online_value
        try:
            await session.flush()
            await session.refresh(user)
            return user
        except Exception as error:
            await session.rollback()
            raise DatabaseError(server_message=f"[User | toggle_online] {error}")

    @staticmethod
    async def set_current_sid(
        session: AsyncSession, user_id: str, new_sid: str | None
    ) -> User:
        user: User = await session.get(User, user_id)
        if not user:
            raise CouldNotFoundUserWithIdError(user_id)
        if not new_sid:
            await UserRepositorty.toggle_online(session, user_id, False)
        user.current_sid = new_sid
        try:
            await session.flush()
            await session.refresh(user)
            return user
        except Exception as error:
            await session.rollback()
            raise DatabaseError(server_message=f"[User | set_current_sid] {error}")

    @staticmethod
    async def update_(session: AsyncSession, user_id: str, update_data: dict) -> User:
        new_data = {
            key: value
            for key, value in update_data.items()
            if key in User.allowed_to_update_fields
        }
        if not new_data:
            raise NothingToUpdateError(
                server_message=f"nothing to update, {update_data} -> {new_data}",
            )
        user: User = await session.get(User, user_id)
        if not user:
            raise CouldNotFoundUserWithIdError(user_id)
        for field, value in new_data.items():
            setattr(user, field, value)
        try:
            await session.flush()
            await session.refresh(user)
            return user
        except Exception as error:
            await session.rollback()
            raise DatabaseError(server_message=f"[User | update] {error}")

    @staticmethod
    async def get_followings(
        session: AsyncSession, target_id: str, pagination: Pagination
    ) -> list[User]:
        target_user = await session.get(User, target_id)
        if not target_user:
            raise CouldNotFoundUserWithIdError(target_id)
        query = (
            select(User)
            .join(user_subscriptions, user_subscriptions.c.following_id == User.id)
            .where(user_subscriptions.c.follower_id == target_id)
            .offset(pagination.offset)
            .limit(pagination.per_page)
        )
        followings = (await session.execute(query)).scalars().all()
        return followings

    @staticmethod
    async def get_followers(
        session: AsyncSession, target_id: str, pagination: Pagination
    ) -> list[User]:
        target_user = await session.get(User, target_id)
        if not target_user:
            raise CouldNotFoundUserWithIdError(target_id)
        query = (
            select(User)
            .join(user_subscriptions, user_subscriptions.c.follower_id == User.id)
            .where(user_subscriptions.c.following_id == target_id)
            .offset(pagination.offset)
            .limit(pagination.per_page)
        )
        followings = (await session.execute(query)).scalars().all()
        return followings

    @staticmethod
    async def update_role(session: AsyncSession, target_id, new_role: Role) -> User:
        target_user: User | None = await session.get(User, target_id)
        if not target_user:
            raise CouldNotFoundUserWithIdError(target_id)
        if new_role == Role.owner:
            existing_owner = await UserRepositorty.get_owner(session)
            if existing_owner:
                raise OwnerAlreadyRegisteredError()
        target_user.role = new_role
        try:
            await session.flush()
            await session.refresh(target_user)
            return target_user
        except Exception as error:
            await session.rollback()
            raise DatabaseError(server_message=f"[User | update_role] {error}")

    @staticmethod
    async def reset_sids(session: AsyncSession) -> None:
        await session.execute(update(User).values(current_sid=None))
        await session.flush()
