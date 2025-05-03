from sqlalchemy import CHAR, Column, ForeignKey, Table

from models.base import BaseModel

post_likes = Table(
    "post_likes",
    BaseModel.metadata,
    Column(
        "user_id",
        CHAR(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "post_id",
        CHAR(36),
        ForeignKey("posts.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
