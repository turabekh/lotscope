from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base
from lotscope.core.mixins import TimestampMixin


class MarketStats(Base, TimestampMixin):
    __tablename__ = "market_stats"

    market_code: Mapped[str] = mapped_column(
        String(10), ForeignKey("market.code"), primary_key=True
    )
    parcel_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    geometry_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    verdict_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    vacant_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    vacant_with_comp_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
