from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    CHAR,
    JSON,
    DateTime,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy import (
    Enum as SqlAlchemyEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel
from models.message_attachment_type import MessageAType

if TYPE_CHECKING:
    from models.chat import Chat
    from models.post import Post
    from models.user import User


class Message(BaseModel):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_chat_id", "chat_id"),
        Index("ix_messages_chat_id_created_at", "chat_id", "created_at"),
        Index("ix_messages_sender_id", "sender_id"),
        Index("ix_messages_recipient_id", "recipient_id"),
        Index("ix_messages_created_at", "created_at"),
    )

    id: Mapped[CHAR] = mapped_column(
        CHAR(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        unique=True,
        nullable=False,
    )
    chat_id: Mapped[str] = mapped_column(
        ForeignKey("chats.id", ondelete="CASCADE"), nullable=False
    )
    sender_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    recipient_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    text_content: Mapped[str] = mapped_column(String(10000), nullable=False, default="")
    attachment_type: Mapped[MessageAType | None] = mapped_column(
        SqlAlchemyEnum(MessageAType), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    attached_image_keys: Mapped[list[str]] = mapped_column(JSON, nullable=True)
    attached_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    attached_post_id: Mapped[str | None] = mapped_column(
        ForeignKey("posts.id", ondelete="SET NULL"), nullable=True
    )

    #* Relationships
    chat: Mapped["Chat"] = relationship(
        "Chat",
        back_populates="messages"
    )

    sender: Mapped["User"] = relationship("User", foreign_keys=[sender_id])
    recipient: Mapped["User"] = relationship("User", foreign_keys=[recipient_id])

    attached_message: Mapped["Message | None"] = relationship(
        "Message",
        foreign_keys=[attached_message_id],
        post_update=True,
    )

    attached_post: Mapped["Post | None"] = relationship("Post", foreign_keys=[attached_post_id])

    def __repr__(self):
        return f"<Message>({self.id}, {self.created_at})"

    # def to_json(self, include_reply=False, detect_rels_for_user_id: str | None = None):
    #     json_view = super().to_json(safe=False, short=False)
    #     json_view["author"] = self.author.to_json(
    #         short=True, detect_rels_for_user_id=detect_rels_for_user_id
    #     )
    #     if include_reply:
    #         json_view["reply_to"] = None
    #         if self.reply_to is not None:
    #             json_view["reply_to"] = self.reply_to.to_json(
    #                 detect_rels_for_user_id=detect_rels_for_user_id
    #             )
    #     if detect_rels_for_user_id:
    #         json_view["is_our"] = detect_rels_for_user_id == self.author_id
    #         json_view["is_our_post"] = detect_rels_for_user_id == self.post.author_id
    #     return json_view
