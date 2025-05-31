from sqlalchemy.orm import load_only, selectinload

from models.chat import Chat
from models.comment import Comment
from models.message import Message
from models.post import Post
from models.user import User

load_short_user_option = load_only(
    User.id,
    User.username,
    User.fullname,
    User.avatar_type,
    User.avatar_key,
    User.deleted_at,
    User.is_online,
)

load_full_post_options: list = [
    selectinload(Post.author).options(
        load_short_user_option,
        selectinload(User.followers).load_only(User.id),
        selectinload(User.following).load_only(User.id),
    ),
    selectinload(Post.comments).load_only(Comment.id),
    selectinload(Post.liked_by).load_only(User.id),
]

load_full_message_options: list = [
    selectinload(Message.sender).options(load_short_user_option),
    selectinload(Message.recipient).options(load_short_user_option),
    selectinload(Message.attached_post).options(*load_full_post_options),
    selectinload(Message.forwarded_from_user).options(load_short_user_option),
]

load_chat_options: list = [
    selectinload(Chat.user1).options(
        load_short_user_option,
    ),
    selectinload(Chat.user2).options(
        load_short_user_option,
    ),
    selectinload(Chat.last_message).options(
        *load_full_message_options,
    ),
]
