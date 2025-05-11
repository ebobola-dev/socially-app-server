
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.comment import Comment
from models.exceptions.api_exceptions import (
    CommentNotFoundError,
    DatabaseError,
)
from models.pagination import Pagination
from models.post import Post
from models.user import User


class CommentsRepository:
    @staticmethod
    async def get_by_id(session: AsyncSession, comment_id: str) -> Comment | None:
        comment = await session.get(Comment, comment_id)
        return comment

    @staticmethod
    async def get_by_id_with_relations(
        session: AsyncSession, comment_id: str
    ) -> Comment | None:
        query = (
            select(Comment)
            .where(Comment.id == comment_id)
            .options(
                selectinload(Comment.author).load_only(
                    User.id,
                    User.username,
                    User.fullname,
                    User.avatar_type,
                    User.avatar_id,
                    User.deleted_at,
                    User.is_online,
                ),
                selectinload(Comment.post).load_only(Post.id),
                selectinload(Comment.reply_to).load_only(Comment.id),
            )
        )
        result = await session.scalars(query)
        return result.first()

    @staticmethod
    async def get_all_by_post_id(
        session: AsyncSession,
        post_id: str,
        pagination=Pagination.default(),
    ) -> list[Comment]:
        query = (
            select(Comment)
            .where(Comment.post_id == post_id)
            .options(
                selectinload(Comment.author).load_only(
                    User.id,
                    User.username,
                    User.fullname,
                    User.avatar_type,
                    User.avatar_id,
                    User.deleted_at,
                    User.is_online,
                ),
                selectinload(Comment.post).load_only(Post.id),
                selectinload(Comment.reply_to),
            )
            .offset(pagination.offset)
            .limit(pagination.limit)
            .order_by(Comment.created_at.desc())
        )
        result = await session.scalars(query)
        return result.all()

    @staticmethod
    async def add(session: AsyncSession, new_comment: Comment) -> Comment:
        session.add(new_comment)
        try:
            await session.flush()
            await session.refresh(new_comment)
            return new_comment
        except Exception as error:
            await session.rollback()
            raise DatabaseError(server_message=f"[Comment | add] {error}")

    @staticmethod
    async def hard_delete(session: AsyncSession, target_comment_id: str) -> None:
        target_comment = await session.get(Comment, target_comment_id)
        if not target_comment:
            raise CommentNotFoundError(target_comment_id)
        await session.delete(target_comment)
        await session.flush()
