from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    CHAR,
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy import (
    Enum as SqlAlchemyEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel, short_fields
from models.exceptions.api_exceptions import (
    InvalidMessageAttachmentError,
)
from models.message_attachment_type import MessageAType

if TYPE_CHECKING:
    from models.post import Post
    from models.user import User


@short_fields(
    "id",
    "text_content",
    "readed",
    "attachment_type",
    "attached_post_id",
    "created_at",
    "deleted_at",
)
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
    readed: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
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
    forwarded_from_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    attached_post_id: Mapped[str | None] = mapped_column(
        ForeignKey("posts.id", ondelete="SET NULL"), nullable=True
    )

    # * Relationships
    chat = relationship("Chat", back_populates="messages", foreign_keys=[chat_id])

    sender: Mapped["User"] = relationship("User", foreign_keys=[sender_id])
    recipient: Mapped["User"] = relationship("User", foreign_keys=[recipient_id])

    attached_post: Mapped["Post | None"] = relationship(
        "Post", foreign_keys=[attached_post_id]
    )

    forwarded_from_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[forwarded_from_user_id],
    )

    def __repr__(self):
        return f"<Message>({self.id}, {self.created_at})"

    @property
    def is_forwarded(self) -> bool:
        return self.forwarded_from_user_id is not None

    @classmethod
    def new(
        cls,
        sender_id: str,
        recipient_id: str,
        text_content: str = "",
        attachment_type: MessageAType | None = None,
        attached_image_keys: list[str] | None = None,
        forwarded_from_user_id: str | None = None,
        attached_post_id: str | None = None,
    ) -> "Message":
        return cls(
            sender_id=sender_id,
            recipient_id=recipient_id,
            text_content=text_content,
            attachment_type=attachment_type,
            attached_image_keys=attached_image_keys,
            forwarded_from_user_id=forwarded_from_user_id,
            attached_post_id=attached_post_id,
        )

    def copy_for_forwarding(
        self,
        sender_id: str,
        recipient_id: str,
    ) -> "Message":
        return Message.new(
            sender_id=sender_id,
            recipient_id=recipient_id,
            text_content=self.text_content,
            attachment_type=self.attachment_type,
            attached_post_id=self.attached_post_id,
            attached_image_keys=self.attached_image_keys,
            forwarded_from_user_id=self.forwarded_from_user_id or self.sender_id,
        )

    @staticmethod
    def validate_attachments(
        text_content: str | None,
        attachment_type: MessageAType | None,
        attached_image_keys: list[str] | None,
        attached_post_id: str | None,
        attached_message_id: str | None,
    ):
        attachment_sources = {
            "image": attached_image_keys,
            "message": attached_message_id,
            "post": attached_post_id,
        }

        present = {
            k: v
            for k, v in attachment_sources.items()
            if v is not None and (not isinstance(v, list) or len(v) > 0)
        }

        if len(present) > 1:
            raise InvalidMessageAttachmentError(
                "Only one type of attachment is allowed"
            )

        if len(present) == 0:
            if not text_content or text_content.strip() == "":
                raise InvalidMessageAttachmentError(
                    "Message must have text or one attachment"
                )

        if len(present) == 1:
            ((key, value),) = present.items()

            if attachment_type is None:
                raise InvalidMessageAttachmentError("Attachment type must be set")

            if key == "image" and attachment_type != MessageAType.images:
                raise InvalidMessageAttachmentError(
                    "Attachment type must be IMAGE for images"
                )
            elif key == "message" and attachment_type != MessageAType.message:
                raise InvalidMessageAttachmentError(
                    "Attachment type must be MESSAGE for forwarded message"
                )
            elif key == "post" and attachment_type != MessageAType.post:
                raise InvalidMessageAttachmentError(
                    "Attachment type must be POST for attached post"
                )
        else:
            if attachment_type is not None:
                raise InvalidMessageAttachmentError(
                    "Attachment type must be None when no attachment present"
                )

    def to_json(
        self,
        short=False,
        detect_rels_for_user_id: str | None = None,
    ):
        json_view = super().to_json(safe=False, short=short)
        if detect_rels_for_user_id:
            json_view["is_our"] = self.sender_id == detect_rels_for_user_id

        # % user pair
        if not short:
            json_view["sender"] = self.sender.to_json(
                short=True,
                detect_rels_for_user_id=detect_rels_for_user_id,
            )
            json_view["recipient"] = self.recipient.to_json(
                short=True,
                detect_rels_for_user_id=detect_rels_for_user_id,
            )

        # % attached post
        if self.attached_post_id:
            json_view["attached_post"] = self.attached_post.to_json(
                short=short,
                detect_rels_for_user_id=detect_rels_for_user_id,
            )
            if short:
                json_view["attached_images_count"] = len(self.attached_post.image_keys)

        # % attached images
        if short and self.attached_image_keys:
            json_view["first_image_key"] = self.attached_image_keys[0]
            json_view["attached_images_count"] = len(self.attached_image_keys)

        # % forwaded message
        json_view["is_forwarded"] = self.is_forwarded
        if self.forwarded_from_user_id:
            if not short:
                json_view["forwarded_from_user"] = self.forwarded_from_user.to_json(
                    detect_rels_for_user_id=detect_rels_for_user_id,
                    short=True,
                )
        return json_view
