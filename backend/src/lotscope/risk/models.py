from datetime import date

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base
from lotscope.core.mixins import IngestionMixin, TimestampMixin


class TaxStatus(Base, TimestampMixin, IngestionMixin):
    __tablename__ = "tax_status"

    parcel_number: Mapped[str] = mapped_column(
        String(40),
        ForeignKey("parcel.parcel_number", ondelete="CASCADE"),
        primary_key=True,
    )
    is_delinquent: Mapped[bool | None] = mapped_column(Boolean)
    delinquency_owner: Mapped[str | None] = mapped_column(String(255))
    snapshot_period: Mapped[str | None] = mapped_column(String(6))
    total_due: Mapped[float | None] = mapped_column(Numeric(14, 2))
    principal_due: Mapped[float | None] = mapped_column(Numeric(14, 2))
    years_owed: Mapped[int | None] = mapped_column(Integer)
    lien_count: Mapped[int | None] = mapped_column(Integer)
    in_sheriff_sale: Mapped[bool | None] = mapped_column(Boolean)
    as_of_date: Mapped[date | None] = mapped_column(Date)


class SheriffSale(Base, TimestampMixin, IngestionMixin):
    __tablename__ = "sheriff_sale"
    __table_args__ = (
        Index("ix_sheriff_sale_parcel_date", "parcel_number", "sale_date"),
        Index("ix_sheriff_sale_date", "sale_date"),
        UniqueConstraint("case_number", name="uq_sheriff_sale_case"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parcel_number: Mapped[str] = mapped_column(
        String(40), ForeignKey("parcel.parcel_number", ondelete="CASCADE"), index=True
    )
    case_number: Mapped[str] = mapped_column(String(60), nullable=False)
    sale_type: Mapped[str | None] = mapped_column(String(30))
    sale_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str | None] = mapped_column(String(40))
    opening_bid: Mapped[float | None] = mapped_column(Numeric(14, 2))
    plaintiff: Mapped[str | None] = mapped_column(Text)


class LiEvent(Base, TimestampMixin, IngestionMixin):
    __tablename__ = "li_event"
    __table_args__ = (
        Index("ix_li_event_parcel_date", "parcel_number", "event_date"),
        UniqueConstraint("event_type", "external_id", name="uq_li_event_type_external"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    parcel_number: Mapped[str] = mapped_column(
        String(40), ForeignKey("parcel.parcel_number", ondelete="CASCADE"), index=True
    )
    external_id: Mapped[str | None] = mapped_column(String(60), index=True)
    event_type: Mapped[str | None] = mapped_column(String(60), index=True)
    status: Mapped[str | None] = mapped_column(String(60))
    case_status: Mapped[str | None] = mapped_column(String(60))
    event_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    is_unsafe: Mapped[bool | None] = mapped_column(Boolean)
    is_imminently_dangerous: Mapped[bool | None] = mapped_column(Boolean)


class FloodZone(Base, TimestampMixin, IngestionMixin):
    __tablename__ = "flood_zone"
    __table_args__ = (UniqueConstraint("external_id", name="uq_flood_zone_external"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str | None] = mapped_column(String(60), index=True)
    zone: Mapped[str | None] = mapped_column(String(60), index=True)

    market_code: Mapped[str] = mapped_column(
        String(10), ForeignKey("market.code"), nullable=False, server_default="phl", index=True
    )
    geom_local: Mapped[WKBElement | None] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=0, spatial_index=True)
    )
    geom_4326: Mapped[WKBElement | None] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=True)
    )
