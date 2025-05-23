from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    CHAR,
    JSON,
    DateTime,
    ForeignKey,
    String,
    inspect,
)
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

from models.base import BaseModel, short_fields

if TYPE_CHECKING:
    from models.comment import Comment
    from models.user import User

@short_fields('id', 'created_at', 'deleted_at')
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
    image_keys: Mapped[list[str]] = mapped_column(JSON, nullable=False)
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
        image_keys: list[str],
    ):
        return Post(
            author_id=author_id,
            text_content=text_content,
            image_keys=image_keys,
        )

    def __repr__(self):
        return f"<Post>({self.id}, {self.created_at}, {self.image_keys})"

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def to_json(self, detect_rels_for_user_id: str | None = None, short: bool = False):
        json_view = super().to_json(safe=False, short=short)
        if short:
            json_view['first_image_key'] = self.image_keys[0]
            return json_view
        json_view["author"] = self.author.to_json(
            short=True, detect_rels_for_user_id=detect_rels_for_user_id
        )

        liked_ids = tuple(map(lambda user: user.id, self.liked_by))
        json_view["likes_count"] = len(liked_ids)

        insp = inspect(self)
        comments = insp.attrs.comments.loaded_value
        if isinstance(comments, list):
            json_view["comments_count"] = len(comments)
        if detect_rels_for_user_id:
            json_view["is_liked"] = detect_rels_for_user_id in liked_ids
            json_view["is_our"] = detect_rels_for_user_id == self.author_id

        return json_view
