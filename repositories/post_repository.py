from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.comment import Comment
from models.exceptions.api_exceptions import (
    AlreadyLikedError,
    DatabaseError,
    NotLikedAnywayError,
    PostNotFoundError,
    UserNotFoundError,
)
from models.pagination import Pagination
from models.post import Post
from models.user import User
from repositories.user_repository import UserRepository


class PostRepository:
    @staticmethod
    async def get_by_id(
        session: AsyncSession, post_id: str, include_deleted: bool = False
    ) -> Post | None:
        post = await session.get(Post, post_id)
        if post and post.is_deleted and not include_deleted:
            return None
        return post

    @staticmethod
    async def get_by_id_with_relations(
        session: AsyncSession, post_id: str, include_deleted: bool = False
    ) -> Post | None:
        query = (
            select(Post)
            .where(Post.id == post_id)
            .options(
                selectinload(Post.author).load_only(
                    User.id,
                    User.username,
                    User.fullname,
                    User.avatar_type,
                    User.avatar_id,
                    User.deleted_at,
                    User.is_online,
                ),
                selectinload(Post.comments).load_only(Comment.id),
                selectinload(Post.liked_by).load_only(User.id),
            )
        )
        if not include_deleted:
            query = query.where(Post.deleted_at.is_(None))
        result = await session.scalars(query)
        return result.first()

    @staticmethod
    async def get_all(
        session: AsyncSession,
        pagination=Pagination.default(),
        include_deleted: bool = False,
        user_id: str | None = None,
    ) -> list[Post]:
        query = (
            select(Post)
            .options(
                selectinload(Post.author).load_only(
                    User.id,
                    User.username,
                    User.fullname,
                    User.avatar_type,
                    User.avatar_id,
                    User.deleted_at,
                    User.is_online,
                ),
                selectinload(Post.comments).load_only(Comment.id),
                selectinload(Post.liked_by).load_only(User.id),
            )
            .offset(pagination.offset)
            .limit(pagination.limit)
            .order_by(Post.created_at.desc())
        )
        if not include_deleted:
            query = query.where(Post.deleted_at.is_(None))
        if user_id:
            query = query.where(Post.author_id == user_id)
        result = await session.scalars(query)
        return result.all()

    @staticmethod
    async def add(session: AsyncSession, new_post: Post) -> Post:
        session.add(new_post)
        try:
            await session.flush()
            await session.refresh(new_post)
            return new_post
        except Exception as error:
            await session.rollback()
            raise DatabaseError(server_message=f"[User | create_new] {error}")

    @staticmethod
    async def soft_delete(session: AsyncSession, target_post_id: str) -> Post:
        target_post = await PostRepository.get_by_id(
            session=session, post_id=target_post_id
        )
        if not target_post:
            raise PostNotFoundError(target_post_id)
        target_post.text_content = ""
        target_post.image_exts = []
        target_post.deleted_at = datetime.now(timezone.utc)
        await session.flush()
        await session.refresh(target_post)
        return target_post

    @staticmethod
    async def like(session: AsyncSession, target_post_id: str, user_id: str):
        target_post = await PostRepository.get_by_id_with_relations(
            session=session, post_id=target_post_id
        )
        user = await UserRepository.get_by_id(
            session=session, user_id=user_id, include_deleted=True
        )
        if not target_post:
            raise PostNotFoundError(target_post_id)
        if not user:
            raise UserNotFoundError(user_id)
        if user in target_post.liked_by:
            raise AlreadyLikedError(user_id, target_post_id)
        target_post.liked_by.append(user)
        try:
            await session.flush()
            await session.refresh(user)
            return target_post
        except Exception as error:
            await session.rollback()
            raise DatabaseError(server_message=f"[Post | set_like] {error}")

    @staticmethod
    async def unlike(session: AsyncSession, target_post_id: str, user_id: str):
        target_post = await PostRepository.get_by_id_with_relations(
            session=session, post_id=target_post_id
        )
        user = await UserRepository.get_by_id(
            session=session, user_id=user_id, include_deleted=True
        )
        if not target_post:
            raise PostNotFoundError(target_post_id)
        if not user:
            raise UserNotFoundError(user_id)
        if user not in target_post.liked_by:
            raise NotLikedAnywayError(user_id, target_post_id)
        target_post.liked_by.remove(user)
        try:
            await session.flush()
            await session.refresh(user)
            return target_post
        except Exception as error:
            await session.rollback()
            raise DatabaseError(server_message=f"[Post | unset_like] {error}")
