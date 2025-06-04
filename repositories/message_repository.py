from datetime import datetime, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    Chat,
    Pagination,
    load_chat_options,
    load_full_message_options,
)
from models.exceptions.api_exceptions import ChatNotFoundError, MessageNotFoundError
from models.message import Message


class MessagesRepository:
    @staticmethod
    async def get_message_by_id(
        session: AsyncSession, message_id: str, include_deleted: bool = False
    ) -> Message | None:
        query = (
            select(Message)
            .where(Message.id == message_id)
            .options(*load_full_message_options)
        )
        if not include_deleted:
            query = query.where(Message.deleted_at.is_(None))
        result = await session.scalars(query)
        return result.first()

    @staticmethod
    async def get_chat_by_id(
        session: AsyncSession, chat_id: str, include_empty: bool = False
    ) -> Chat | None:
        query = (
            select(Chat)
            .where(
                and_(Chat.id == chat_id),
            )
            .options(*load_chat_options)
        )
        if not include_empty:
            query = query.where(Chat.last_message_id.is_not(None))
        result = await session.scalars(query)
        return result.first()

    @staticmethod
    async def get_chat_by_user_pair(
        session: AsyncSession,
        uid1: str,
        uid2: str,
        include_empty: bool = False,
    ) -> Chat | None:
        uid1, uid2 = sorted([uid1, uid2])
        query = (
            select(Chat)
            .where(
                and_(Chat.user1_id == uid1, Chat.user2_id == uid2),
            )
            .options(*load_chat_options)
        )
        if not include_empty:
            query = query.where(Chat.last_message_id.is_not(None))
        result = await session.scalars(query)
        return result.first()

    @staticmethod
    async def get_chats_by_user_id(
        session: AsyncSession,
        user_id: str,
        pagination=Pagination.default(),
    ) -> list[Chat]:
        query = (
            select(Chat)
            .where(
                and_(
                    or_(
                        Chat.user1_id == user_id,
                        Chat.user2_id == user_id,
                    ),
                    Chat.last_message_id.is_not(None),
                ),
            )
            .options(*load_chat_options)
            .offset(pagination.offset)
            .limit(pagination.limit)
            .order_by(Chat.last_message_created_at.desc())
        )
        result = await session.scalars(query)
        return result.all()

    @staticmethod
    async def get_messages(
        session: AsyncSession,
        current_user_id: str,
        other_user_id: str,
        pagination=Pagination.default(),
    ) -> list[Message]:
        user1_id, user2_id = sorted([current_user_id, other_user_id])
        chat_query = select(Chat).where(
            and_(
                Chat.user1_id == user1_id,
                Chat.user2_id == user2_id,
            )
        )
        chat_result = await session.scalar(chat_query)
        if not chat_result:
            return []
        messages_query = (
            select(Message)
            .where(
                and_(Message.chat_id == chat_result.id, Message.deleted_at.is_(None))
            )
            .options(*load_full_message_options)
            .order_by(Message.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        messages_result = await session.scalars(messages_query)
        return messages_result.all()

    @staticmethod
    async def soft_delete_message(
        session: AsyncSession,
        target_message_id: str,
    ) -> tuple[Message, Message | None]:
        target_message = await MessagesRepository.get_message_by_id(
            session=session,
            message_id=target_message_id,
        )
        if not target_message:
            raise MessageNotFoundError(target_message_id)

        target_message.text_content = ""
        target_message.attachment_type = None
        target_message.attached_images_count = None
        target_message.attached_post_id = None
        target_message.forwarded_from_user_id = None

        chat = await MessagesRepository.get_chat_by_id(
            session=session,
            chat_id=target_message.chat_id,
        )
        if not chat:
            raise ChatNotFoundError(target_message.chat_id)
        previous_message = await session.scalar(
            select(Message)
            .where(
                Message.chat_id == chat.id,
                Message.deleted_at.is_(None),
                Message.id != target_message_id,
            )
            .options(*load_full_message_options)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        if chat.last_message_id == target_message_id:
            if previous_message:
                chat.last_message_id = previous_message.id
                chat.last_message_created_at = previous_message.created_at
            else:
                chat.last_message_id = None
                chat.last_message_created_at = None

        target_message.deleted_at = datetime.now(timezone.utc)
        await session.flush()
        return target_message, previous_message

    @staticmethod
    async def create_chat(
        session: AsyncSession,
        uid1: str,
        uid2: str,
    ) -> Chat:
        uid1, uid2 = sorted([uid1, uid2])
        chat = Chat.new(
            user1_id=uid1,
            user2_id=uid2,
        )
        session.add(chat)
        await session.flush()
        return chat

    @staticmethod
    async def create_message(
        session: AsyncSession,
        message: Message,
    ) -> Message:
        chat = await MessagesRepository.get_chat_by_user_pair(
            session=session,
            uid1=message.sender_id,
            uid2=message.recipient_id,
            include_empty=True,
        )
        if not chat:
            chat = await MessagesRepository.create_chat(
                session=session,
                uid1=message.sender_id,
                uid2=message.recipient_id,
            )
        message.chat_id = chat.id
        session.add(message)
        await session.flush()
        chat.last_message_id = message.id
        chat.last_message_created_at = message.created_at
        await session.flush()
        return message

    @staticmethod
    async def mark_readed(
        session: AsyncSession,
        message_id: str,
    ) -> Message:
        message = await MessagesRepository.get_message_by_id(
            session=session,
            message_id=message_id,
        )
        if not message:
            raise MessageNotFoundError(message_id)
        message.readed = True
        await session.flush()
        return message
