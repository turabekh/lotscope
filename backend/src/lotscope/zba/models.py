from datetime import date

from sqlalchemy import Date, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base
from lotscope.core.mixins import IngestionMixin, TimestampMixin


class ZbaAppeal(Base, TimestampMixin, IngestionMixin):
    __tablename__ = "zba_appeal"
    __table_args__ = (
        UniqueConstraint("appeal_number", name="uq_zba_appeal_number"),
        Index("ix_zba_appeal_parcel_decision", "parcel_number", "decision"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    appeal_number: Mapped[str] = mapped_column(String(40), nullable=False)
    parcel_number: Mapped[str | None] = mapped_column(String(20), index=True)
    appeal_type: Mapped[str | None] = mapped_column(String(60), index=True)
    decision: Mapped[str | None] = mapped_column(String(40), index=True)
    decision_date: Mapped[date | None] = mapped_column(Date)
    address: Mapped[str | None] = mapped_column(String(160))
