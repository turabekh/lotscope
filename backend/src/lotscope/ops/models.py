from datetime import datetime

from sqlalchemy import (
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base
from lotscope.core.mixins import TimestampMixin


class MarketStats(Base, TimestampMixin):
    __tablename__ = "market_stats"

    market_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    parcel_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    geometry_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    screened_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    vacant_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    vacant_priced_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OpsAlertState(Base, TimestampMixin):
    __tablename__ = "ops_alert_state"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    last_job_run_id: Mapped[int | None] = mapped_column(Integer)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ErrorEvent(Base, TimestampMixin):
    """One kind of unhandled failure, counted, not one row per occurrence.

    The fingerprint is the dedup: exception type plus where it happened. A loop that
    throws the same error four thousand times in a quarter of an hour is one line in the
    digest with a count of four thousand, because four thousand emails and one email
    carry the same information and only one of them gets read.

    `context` holds what the reader needs to reproduce it — the request's method and
    path, or the job's name and arguments — and `sample` the last message seen, so the
    digest can show a real error rather than only a class name.
    """

    __tablename__ = "error_event"

    fingerprint: Mapped[str] = mapped_column(String(200), primary_key=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    kind: Mapped[str] = mapped_column(String(120), nullable=False)
    where: Mapped[str] = mapped_column(String(200), nullable=False)
    sample: Mapped[str | None] = mapped_column(Text)
    context: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    occurrences: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notified_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
