from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.exceptions.api_exceptions import DatabaseError, PostNotFoundError
from models.pagination import Pagination
from models.post import Post


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
                selectinload(Post.author),
                selectinload(Post.comments),
                selectinload(Post.liked_by),
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
    ) -> list[Post]:
        query = (
            select(Post)
            .options(
                selectinload(Post.author),
                selectinload(Post.comments),
                selectinload(Post.liked_by),
            )
            .offset(pagination.offset)
            .limit(pagination.per_page)
        )
        if not include_deleted:
            query = query.where(Post.deleted_at.is_(None))
        result = await session.scalars(query)
        return result.all()

    @staticmethod
    async def get_all_of_user(
        session: AsyncSession,
        user_id: str,
        pagination=Pagination.default(),
        include_deleted: bool = False,
    ) -> list[Post]:
        query = (
            select(Post)
            .where(Post.author_id == user_id)
            .options(
                selectinload(Post.author),
                selectinload(Post.comments),
                selectinload(Post.liked_by),
            )
            .offset(pagination.offset)
            .limit(pagination.per_page)
        )
        if not include_deleted:
            query = query.where(Post.deleted_at.is_(None))
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
            raise PostNotFoundError()
        target_post.text_content = ""
        target_post.image_exts = []
        target_post.deleted_at = datetime.now(timezone.utc)
        await session.flush()
        await session.refresh(target_post)
        return target_post
