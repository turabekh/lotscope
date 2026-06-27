from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base
from lotscope.core.mixins import IngestionMixin, TimestampMixin


class TaxStatus(Base, TimestampMixin, IngestionMixin):
    __tablename__ = "tax_status"

    parcel_number: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("parcel.parcel_number", ondelete="CASCADE"),
        primary_key=True,
    )
    is_delinquent: Mapped[bool | None] = mapped_column(Boolean)
    total_due: Mapped[float | None] = mapped_column(Numeric(14, 2))
    principal_due: Mapped[float | None] = mapped_column(Numeric(14, 2))
    years_owed: Mapped[int | None] = mapped_column(Integer)
    lien_count: Mapped[int | None] = mapped_column(Integer)
    in_sheriff_sale: Mapped[bool | None] = mapped_column(Boolean)
    as_of_date: Mapped[date | None] = mapped_column(Date)


class LiEvent(Base, TimestampMixin, IngestionMixin):
    __tablename__ = "li_event"
    __table_args__ = (Index("ix_li_event_parcel_date", "parcel_number", "event_date"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    parcel_number: Mapped[str] = mapped_column(
        String(20), ForeignKey("parcel.parcel_number", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str | None] = mapped_column(String(60), index=True)
    status: Mapped[str | None] = mapped_column(String(60))
    event_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    is_unsafe: Mapped[bool | None] = mapped_column(Boolean)
    is_imminently_dangerous: Mapped[bool | None] = mapped_column(Boolean)
