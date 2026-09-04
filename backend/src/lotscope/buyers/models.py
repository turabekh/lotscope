from datetime import date, datetime

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import (
    Date,
    DateTime,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base
from lotscope.core.mixins import IngestionMixin, TimestampMixin


class BuyerProfile(Base, TimestampMixin, IngestionMixin):
    __tablename__ = "buyer_profile"
    __table_args__ = (
        UniqueConstraint("market_code", "buyer_key", name="uq_buyer_profile_market_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    market_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    buyer_key: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    purchases_window: Mapped[int] = mapped_column(Integer, nullable=False)
    lot_purchases_window: Mapped[int] = mapped_column(Integer, nullable=False)
    last_purchase_at: Mapped[date | None] = mapped_column(Date)
    median_price: Mapped[float | None] = mapped_column(Numeric(14, 2))
    total_consideration: Mapped[float | None] = mapped_column(Numeric(16, 2))
    mailing_address: Mapped[str | None] = mapped_column(String(255))
    activity_centroid: Mapped[WKBElement | None] = mapped_column(
        Geometry(geometry_type="POINT", srid=0, spatial_index=True)
    )
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
