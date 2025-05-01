from sqlalchemy import CHAR, Column, ForeignKey, Table

from models.base import BaseModel

user_subscriptions = Table(
    "user_subscriptions",
    BaseModel.metadata,
    Column(
        "follower_id",
        CHAR(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "following_id",
        CHAR(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
