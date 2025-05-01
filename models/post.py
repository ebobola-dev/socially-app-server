from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    CHAR,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    images_count: Mapped[int] = mapped_column(Integer, nullable=False)
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

    @staticmethod
    def new(
        author_id: str,
        text_content: str = "",
    ):
        return Post(
            author_id=author_id,
            text_content=text_content,
        )

    def __repr__(self):
        return f"<Post>({self.id}, {self.created_at})"

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
