from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    CHAR,
    JSON,
    DateTime,
    ForeignKey,
    String,
)
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

from models.base import BaseModel

if TYPE_CHECKING:
    from models.comment import Comment
    from models.user import User


class Post(BaseModel):
    __tablename__ = "posts"

    id: Mapped[CHAR] = mapped_column(
        CHAR(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        unique=True,
        nullable=False,
    )
    author_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    text_content: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    image_exts: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    author: Mapped["User"] = relationship(
        "User",
        back_populates="posts",
        passive_deletes=True,
    )

    comments: Mapped[list["Comment"]] = relationship(
        "Comment",
        back_populates="post",
        cascade="save-update, merge",
        passive_deletes=True,
    )

    liked_by = relationship(
        "User",
        secondary="post_likes",
        backref=backref("liked_posts", lazy="selectin"),
        lazy="selectin",
        cascade="all, delete",
        passive_deletes=True,
    )

    @staticmethod
    def new(
        author_id: str,
        text_content: str,
        image_exts: list[str],
    ):
        return Post(
            author_id=author_id,
            text_content=text_content,
            image_exts=image_exts,
        )

    def __repr__(self):
        return f"<Post>({self.id}, {self.created_at}, {self.image_exts})"

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
