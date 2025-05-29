from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    CHAR,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel

if TYPE_CHECKING:
    from models.message import Message
    from models.user import User


class Chat(BaseModel):
    __tablename__ = "chats"
    __table_args__ = (
        UniqueConstraint("user1_id", "user2_id", name="uq_chats_user_pair"),
        Index("ix_chats_user1_user2", "user1_id", "user2_id", unique=True),
        Index("ix_chats_last_message_created_at", "last_message_created_at"),
    )

    id: Mapped[str] = mapped_column(
        CHAR(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        unique=True,
    )
    user1_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    user2_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    last_message_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "messages.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_chats_last_message_id",
            deferrable=True,
        ),
        nullable=True,
    )
    last_message_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    #* Relationships
    user1: Mapped["User"] = relationship("User", foreign_keys=[user1_id])
    user2: Mapped["User"] = relationship("User", foreign_keys=[user2_id])

    last_message: Mapped["Message | None"] = relationship("Message", foreign_keys=[last_message_id])

    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="chat",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys='Message.chat_id',
    )

    def __repr__(self):
        return f"<Chat>({self.user1_id} <-> {self.user2_id})"

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
