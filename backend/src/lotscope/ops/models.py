from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
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


class MarketGateItem(Base, TimestampMixin):
    __tablename__ = "market_gate_item"
    __table_args__ = (
        UniqueConstraint(
            "market_code", "gate_type", "ordinal", name="uq_market_gate_item_market_type_ordinal"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market_code: Mapped[str] = mapped_column(
        String(10), ForeignKey("market.code"), nullable=False, index=True
    )
    gate_type: Mapped[str] = mapped_column(String(20), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    satisfied: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    qualifier: Mapped[str | None] = mapped_column(String(80))
    threshold: Mapped[str | None] = mapped_column(String(80))
    measured: Mapped[str | None] = mapped_column(Text)
    owner: Mapped[str | None] = mapped_column(String(80))
    evidence: Mapped[str | None] = mapped_column(Text)
    spec_ref: Mapped[str | None] = mapped_column(String(40))
    as_of: Mapped[date | None] = mapped_column(Date)


class OpsAlertState(Base, TimestampMixin):
    __tablename__ = "ops_alert_state"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    last_job_run_id: Mapped[int | None] = mapped_column(Integer)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
