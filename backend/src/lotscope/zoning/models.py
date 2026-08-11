from datetime import date
from typing import Any

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base
from lotscope.core.mixins import IngestionMixin, TimestampMixin


class ZoningDistrict(Base, TimestampMixin, IngestionMixin):
    __tablename__ = "zoning_district"
    __table_args__ = (UniqueConstraint("external_id", name="uq_zoning_district_external"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str | None] = mapped_column(String(60), index=True)
    code: Mapped[str] = mapped_column(String(20), index=True)
    category: Mapped[str | None] = mapped_column(String(60))
    long_code: Mapped[str | None] = mapped_column(String(60))

    market_code: Mapped[str] = mapped_column(
        String(10), ForeignKey("market.code"), nullable=False, server_default="phl", index=True
    )
    geom_local: Mapped[WKBElement | None] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=0, spatial_index=True)
    )
    geom_4326: Mapped[WKBElement | None] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=True)
    )


class ZoningOverlay(Base, TimestampMixin, IngestionMixin):
    __tablename__ = "zoning_overlay"
    __table_args__ = (UniqueConstraint("external_id", name="uq_zoning_overlay_external"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str | None] = mapped_column(String(60), index=True)
    code: Mapped[str | None] = mapped_column(String(30), index=True)
    name: Mapped[str | None] = mapped_column(String(255), index=True)
    code_section: Mapped[str | None] = mapped_column(String(60))

    market_code: Mapped[str] = mapped_column(
        String(10), ForeignKey("market.code"), nullable=False, server_default="phl", index=True
    )
    geom_local: Mapped[WKBElement | None] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=0, spatial_index=True)
    )
    geom_4326: Mapped[WKBElement | None] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=True)
    )


class Rco(Base, TimestampMixin, IngestionMixin):
    __tablename__ = "rco"
    __table_args__ = (UniqueConstraint("external_id", name="uq_rco_external"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str | None] = mapped_column(String(60), index=True)
    name: Mapped[str | None] = mapped_column(String(255), index=True)
    org_type: Mapped[str | None] = mapped_column(String(60))

    market_code: Mapped[str] = mapped_column(
        String(10), ForeignKey("market.code"), nullable=False, server_default="phl", index=True
    )
    geom_local: Mapped[WKBElement | None] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=0, spatial_index=True)
    )
    geom_4326: Mapped[WKBElement | None] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=True)
    )


class ZoningStandard(Base, TimestampMixin):
    __tablename__ = "zoning_standard"
    __table_args__ = (
        UniqueConstraint(
            "market_code", "code", "code_version", name="uq_zoning_standard_market_code_version"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market_code: Mapped[str] = mapped_column(
        String(10), ForeignKey("market.code"), nullable=False, server_default="phl", index=True
    )
    code: Mapped[str] = mapped_column(String(20), index=True)
    code_version: Mapped[str] = mapped_column(String(40))
    source: Mapped[str | None] = mapped_column(String(255))
    effective_date: Mapped[date | None] = mapped_column(Date)

    permitted_uses: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    dimensional: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    field_dispositions: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    min_lot_area_sqft: Mapped[float | None] = mapped_column(Numeric(12, 2))
    min_lot_width_ft: Mapped[float | None] = mapped_column(Numeric(10, 2))
    max_height_ft: Mapped[float | None] = mapped_column(Numeric(10, 2))
    max_units: Mapped[int | None] = mapped_column(Integer)
    lot_area_per_unit_sqft: Mapped[float | None] = mapped_column(Numeric(12, 2))
    max_floor_area_ratio_pct: Mapped[float | None] = mapped_column(Numeric(8, 2))
    max_occupancy_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    front_setback_ft: Mapped[float | None] = mapped_column(Numeric(10, 2))
    side_setback_ft: Mapped[float | None] = mapped_column(Numeric(10, 2))
    rear_setback_ft: Mapped[float | None] = mapped_column(Numeric(10, 2))
    requires_master_plan: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )


class OverlayStandard(Base, TimestampMixin):
    __tablename__ = "overlay_standard"
    __table_args__ = (
        UniqueConstraint(
            "market_code",
            "code_section",
            "district_code",
            "field",
            "code_version",
            name="uq_overlay_standard_scope",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market_code: Mapped[str] = mapped_column(
        String(10), ForeignKey("market.code"), nullable=False, server_default="phl", index=True
    )
    code_section: Mapped[str] = mapped_column(String(60), index=True)
    overlay_code: Mapped[str] = mapped_column(String(30))
    district_code: Mapped[str] = mapped_column(String(20), index=True)
    field: Mapped[str] = mapped_column(String(40))
    value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    citation: Mapped[str] = mapped_column(String(60))
    code_version: Mapped[str] = mapped_column(String(40))
