from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base
from lotscope.core.mixins import TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "app_user"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default="user")
    tier: Mapped[str] = mapped_column(String(20), nullable=False, server_default="free")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), index=True)
    subscription_status: Mapped[str | None] = mapped_column(String(40))
    digest_frequency: Mapped[str] = mapped_column(
        String(10), nullable=False, default="weekly", server_default="weekly"
    )
