from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base
from lotscope.core.mixins import TimestampMixin


class DatasetFreshness(Base, TimestampMixin):
    __tablename__ = "dataset_freshness"

    dataset: Mapped[str] = mapped_column(String(120), primary_key=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="unknown")
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    row_count: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[str | None] = mapped_column(Text)


class IngestRun(Base):
    __tablename__ = "ingest_run"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dataset: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="running")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    merged_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class RawRecord(Base):
    __tablename__ = "raw_record"
    __table_args__ = ({"schema": "raw"},)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ingest_run_id: Mapped[int] = mapped_column(
        ForeignKey("ingest_run.id", ondelete="CASCADE"), index=True, nullable=False
    )
    dataset: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    natural_key: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ParcelEvent(Base):
    __tablename__ = "parcel_event"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    parcel_number: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("parcel.parcel_number", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    dataset: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    old_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    new_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    ingest_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("ingest_run.id", ondelete="SET NULL")
    )


class StagingTax(Base):
    __tablename__ = "tax"
    __table_args__ = ({"schema": "staging"},)

    parcel_number: Mapped[str] = mapped_column(String(20), primary_key=True)
    ingest_run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    is_delinquent: Mapped[bool | None] = mapped_column(Boolean)
    total_due: Mapped[float | None] = mapped_column(Numeric(14, 2))
    principal_due: Mapped[float | None] = mapped_column(Numeric(14, 2))
    years_owed: Mapped[int | None] = mapped_column(Integer)
    lien_count: Mapped[int | None] = mapped_column(Integer)
    in_sheriff_sale: Mapped[bool | None] = mapped_column(Boolean)
    as_of_date: Mapped[date | None] = mapped_column(Date)
