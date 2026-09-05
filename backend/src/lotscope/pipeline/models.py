from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base
from lotscope.core.mixins import TimestampMixin


class Deal(Base, TimestampMixin):
    __tablename__ = "deal"
    __table_args__ = (UniqueConstraint("user_id", "parcel_number", name="uq_deal_user_parcel"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), index=True)
    parcel_number: Mapped[str] = mapped_column(
        String(40), ForeignKey("parcel.parcel_number", ondelete="CASCADE")
    )
    stage: Mapped[str] = mapped_column(String(20), nullable=False, server_default="lead")
    note: Mapped[str | None] = mapped_column(Text)
    target_price: Mapped[float | None] = mapped_column(Numeric(14, 2))
    next_action: Mapped[str | None] = mapped_column(Text)
    next_action_due: Mapped[date | None] = mapped_column(Date, index=True)
    stage_entered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contact_name: Mapped[str | None] = mapped_column(String(160))
    contact_phone: Mapped[str | None] = mapped_column(String(40))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    agent_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_run.id", ondelete="SET NULL"), nullable=True
    )


class DealActivity(Base, TimestampMixin):
    __tablename__ = "deal_activity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deal_id: Mapped[int] = mapped_column(
        ForeignKey("deal.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    from_stage: Mapped[str | None] = mapped_column(String(20))
    to_stage: Mapped[str | None] = mapped_column(String(20))
    body: Mapped[str | None] = mapped_column(Text)
