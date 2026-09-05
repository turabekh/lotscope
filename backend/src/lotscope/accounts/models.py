from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
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
    tier: Mapped[str] = mapped_column(String(20), nullable=False, server_default="user")
    comp_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), index=True)
    subscription_status: Mapped[str | None] = mapped_column(String(40))
    digest_frequency: Mapped[str] = mapped_column(
        String(10), nullable=False, default="weekly", server_default="weekly"
    )
    onboarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_verification_nonce: Mapped[str | None] = mapped_column(String(64))
    entity_name: Mapped[str | None] = mapped_column(String(255))
    signer_name: Mapped[str | None] = mapped_column(String(255))
    signer_phone: Mapped[str | None] = mapped_column(String(40))
    signer_email: Mapped[str | None] = mapped_column(String(255))


class Purchase(Base):
    __tablename__ = "purchase"
    __table_args__ = (
        UniqueConstraint("stripe_session_id", name="uq_purchase_stripe_session"),
        Index("ix_purchase_user_sku_object", "user_id", "sku", "object_ref"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    sku: Mapped[str] = mapped_column(String(20), nullable=False)
    stripe_session_id: Mapped[str] = mapped_column(String(255), nullable=False)
    object_ref: Mapped[str] = mapped_column(String(80), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class BuyerInvite(Base):
    __tablename__ = "buyer_invite"
    __table_args__ = (UniqueConstraint("code", name="uq_buyer_invite_code"),)

    buyer_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    redeemed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
