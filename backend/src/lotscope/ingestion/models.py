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
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
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


class StagingOpa(Base):
    __tablename__ = "opa"
    __table_args__ = ({"schema": "staging"},)

    parcel_number: Mapped[str] = mapped_column(String(20), primary_key=True)
    ingest_run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    address: Mapped[str | None] = mapped_column(String(255))
    zip_code: Mapped[str | None] = mapped_column(String(20))
    owner: Mapped[str | None] = mapped_column(String(255))
    mailing_address: Mapped[str | None] = mapped_column(String(255))
    land_use: Mapped[str | None] = mapped_column(String(120))
    base_zoning_code: Mapped[str | None] = mapped_column(String(20))
    market_value: Mapped[float | None] = mapped_column(Numeric(14, 2))
    land_value: Mapped[float | None] = mapped_column(Numeric(14, 2))
    improvement_value: Mapped[float | None] = mapped_column(Numeric(14, 2))
    exempt_land: Mapped[float | None] = mapped_column(Numeric(14, 2))
    exempt_building: Mapped[float | None] = mapped_column(Numeric(14, 2))
    lot_area_sqft: Mapped[float | None] = mapped_column(Numeric(14, 2))
    frontage_ft: Mapped[float | None] = mapped_column(Numeric(10, 2))
    depth_ft: Mapped[float | None] = mapped_column(Numeric(10, 2))


class StagingRtt(Base):
    __tablename__ = "rtt"
    __table_args__ = ({"schema": "staging"},)

    parcel_number: Mapped[str] = mapped_column(String(20), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    ingest_run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    document_type: Mapped[str | None] = mapped_column(String(60))
    sale_date: Mapped[date | None] = mapped_column(Date)
    sale_price: Mapped[float | None] = mapped_column(Numeric(14, 2))
    grantor: Mapped[str | None] = mapped_column(Text)
    grantee: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(120))


class StagingSheriffSale(Base):
    __tablename__ = "sheriff_sale"
    __table_args__ = ({"schema": "staging"},)

    case_number: Mapped[str] = mapped_column(String(60), primary_key=True)
    ingest_run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    parcel_number: Mapped[str] = mapped_column(String(20), nullable=False)
    sale_type: Mapped[str | None] = mapped_column(String(30))
    sale_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str | None] = mapped_column(String(40))
    opening_bid: Mapped[float | None] = mapped_column(Numeric(14, 2))
    plaintiff: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(120))


class StagingLiEvent(Base):
    __tablename__ = "li_event"
    __table_args__ = ({"schema": "staging"},)

    event_type: Mapped[str] = mapped_column(String(60), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(60), primary_key=True)
    ingest_run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    parcel_number: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str | None] = mapped_column(String(60))
    event_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    is_unsafe: Mapped[bool | None] = mapped_column(Boolean)
    is_imminently_dangerous: Mapped[bool | None] = mapped_column(Boolean)
    source: Mapped[str | None] = mapped_column(String(120))
