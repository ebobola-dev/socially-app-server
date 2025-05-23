from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    CHAR,
    DateTime,
    ForeignKey,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel

if TYPE_CHECKING:
    from models.post import Post
    from models.user import User


class Comment(BaseModel):
    __tablename__ = "comments"

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
    post_id: Mapped[str] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    reply_to_comment_id: Mapped[str | None] = mapped_column(
        ForeignKey("comments.id", ondelete="SET NULL"), nullable=True
    )
    text_content: Mapped[str] = mapped_column(String(2048), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    author: Mapped["User"] = relationship(
        "User",
        back_populates="comments",
        passive_deletes=True,
    )

    post: Mapped["Post"] = relationship(
        "Post", back_populates="comments", passive_deletes=True
    )

    reply_to: Mapped["Comment"] = relationship(
        "Comment",
        remote_side=[id],
        backref="replies",
        passive_deletes=True,
    )

    @staticmethod
    def new(
        author_id: str,
        post_id: str,
        text_content: str,
        reply_to_comment_id: str | None = None,
    ):
        return Comment(
            author_id=author_id,
            post_id=post_id,
            text_content=text_content,
            reply_to_comment_id=reply_to_comment_id,
        )

    def __repr__(self):
        return f"<Comment>({self.id}, {self.created_at})"

    def to_json(self, include_reply=False, detect_rels_for_user_id: str | None = None):
        json_view = super().to_json(safe=False, short=False)
        json_view["author"] = self.author.to_json(
            short=True, detect_rels_for_user_id=detect_rels_for_user_id
        )
        if include_reply:
            json_view["reply_to"] = None
            if self.reply_to is not None:
                json_view["reply_to"] = self.reply_to.to_json(
                    detect_rels_for_user_id=detect_rels_for_user_id
                )
        if detect_rels_for_user_id:
            json_view["is_our"] = detect_rels_for_user_id == self.author_id
            json_view["is_our_post"] = detect_rels_for_user_id == self.post.author_id
        return json_view
