"""Overnight findings, one row per user per thing that changed.

A signal is only ever built from a row that already exists somewhere else: a sheriff event, a
deed, a violation, a filing. It carries the table and row id that produced it, so every line
in a brief can be traced back to the record it came from rather than to the model's memory.

`signal_key` makes the nightly build idempotent: running it twice on the same day, or
re-running it after a failure, produces the same rows rather than a duplicate brief.
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base

SIGNAL_KINDS = (
    "sale_status",
    "neighbor_delinquency",
    "neighbor_violation",
    "neighbor_deed",
    "zba_filing",
    "new_listing",
    "alert",
)


class AnalystSignal(Base):
    __tablename__ = "analyst_signal"
    __table_args__ = (
        UniqueConstraint("user_id", "signal_key", name="uq_analyst_signal_user_key"),
        Index("ix_analyst_signal_user_day", "user_id", "signal_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    signal_key: Mapped[str] = mapped_column(String(200), nullable=False)
    signal_date: Mapped[date] = mapped_column(Date, nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    parcel_number: Mapped[str | None] = mapped_column(String(40), index=True)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")

    # Provenance: the dataset, a URL a person can open, and the exact row behind this line.
    source: Mapped[str] = mapped_column(String(60), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    source_table: Mapped[str] = mapped_column(String(60), nullable=False)
    source_row_id: Mapped[str] = mapped_column(String(80), nullable=False)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AnalystBrief(Base):
    __tablename__ = "analyst_brief"
    __table_args__ = (UniqueConstraint("user_id", "brief_date", name="uq_analyst_brief_user_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    brief_date: Mapped[date] = mapped_column(Date, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    signal_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    emailed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    run_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_run.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
