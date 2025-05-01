from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    BINARY,
    BOOLEAN,
    CHAR,
    DATE,
    DateTime,
    String,
)
from sqlalchemy import (
    Enum as SqlAlchemyEnum,
)
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

from models.avatar_type import AvatarType
from models.base import (
    BaseModel,
    allowed_to_update_fields,
    protected_from_json_fields,
    relationship_fields,
    safe_fields,
    short_fields,
)
from models.gender import Gender
from models.role import Role
from models.user_subscriptions import user_subscriptions

if TYPE_CHECKING:
    from models.comment import Comment
    from models.post import Post


@safe_fields("email_address")
@protected_from_json_fields("hashed_password", "current_sid")
@relationship_fields("following", "followers")
@short_fields(
    "id", "username", "fullname", "avatar_id", "avatar_type", "is_online", "deleted_at"
)
@allowed_to_update_fields(
    "username",
    "hashed_password",
    "fullname",
    "date_of_birth",
    "gender",
    "about_me",
    "role",
    "avatar_type",
    "is_registration_completed",
    "is_online",
    "current_sid",
    "last_seen",
    "avatar_id",
)
class User(BaseModel):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        CHAR(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        unique=True,
        nullable=False,
    )
    email_address: Mapped[str] = mapped_column(
        String(320), unique=True, nullable=False
    )
    username: Mapped[str] = mapped_column(String(16), unique=True, nullable=True)
    hashed_password: Mapped[bytes] = mapped_column(BINARY(60), nullable=True)
    fullname: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    date_of_birth: Mapped[date] = mapped_column(DATE(), nullable=True)
    gender: Mapped[Gender | None] = mapped_column(
        SqlAlchemyEnum(Gender), nullable=True
    )
    about_me: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    role: Mapped[Role] = mapped_column(
        SqlAlchemyEnum(Role), nullable=False, default=Role.user
    )
    avatar_type: Mapped[AvatarType | None] = mapped_column(
        SqlAlchemyEnum(AvatarType), nullable=True
    )
    avatar_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    is_registration_completed: Mapped[BOOLEAN] = mapped_column(
        BOOLEAN(), nullable=False, default=False
    )
    is_online: Mapped[bool] = mapped_column(BOOLEAN(), nullable=False, default=False)
    current_sid: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_seen: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    following = relationship(
        "User",
        secondary=user_subscriptions,
        primaryjoin=(id == user_subscriptions.c.follower_id),
        secondaryjoin=(id == user_subscriptions.c.following_id),
        backref=backref("followers", lazy="selectin"),
        lazy="selectin",
        cascade="all, delete",
        passive_deletes=True,
    )

    refresh_tokens = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )

    posts: Mapped[list["Post"]] = relationship(
        "Post",
        back_populates="author",
        cascade="save-update, merge",
        passive_deletes=True,
    )

    comments: Mapped[list["Comment"]] = relationship(
        "Comment",
        back_populates="author",
        cascade="save-update, merge",
        passive_deletes=True,
    )

    @staticmethod
    def new(email, role: Role = Role.user):
        return User(
            email_address=email,
            role=role,
        )

    def __repr__(self):
        return f"<User>({self.id}, {self.role}, email: {self.email_address})"

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
