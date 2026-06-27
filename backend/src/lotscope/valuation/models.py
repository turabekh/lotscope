from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base
from lotscope.core.mixins import IngestionMixin, TimestampMixin


class Sale(Base, TimestampMixin, IngestionMixin):
    __tablename__ = "sale"
    __table_args__ = (Index("ix_sale_parcel_date", "parcel_number", "sale_date"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    parcel_number: Mapped[str] = mapped_column(
        String(20), ForeignKey("parcel.parcel_number", ondelete="CASCADE"), index=True
    )
    document_id: Mapped[str | None] = mapped_column(String(40), index=True)
    document_type: Mapped[str | None] = mapped_column(String(60))

    sale_date: Mapped[date | None] = mapped_column(Date)
    sale_price: Mapped[float | None] = mapped_column(Numeric(14, 2))

    grantor: Mapped[str | None] = mapped_column(String(255))
    grantee: Mapped[str | None] = mapped_column(String(255))
