from datetime import date
from typing import Any

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import Date, Integer, Numeric, String, UniqueConstraint
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

    geom_2272: Mapped[WKBElement | None] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=2272, spatial_index=True)
    )
    geom_4326: Mapped[WKBElement | None] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=True)
    )


class ZoningStandard(Base, TimestampMixin):
    __tablename__ = "zoning_standard"
    __table_args__ = (
        UniqueConstraint("code", "code_version", name="uq_zoning_standard_code_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), index=True)
    code_version: Mapped[str] = mapped_column(String(40))
    source: Mapped[str | None] = mapped_column(String(255))
    effective_date: Mapped[date | None] = mapped_column(Date)

    permitted_uses: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    dimensional: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")

    min_lot_area_sqft: Mapped[float | None] = mapped_column(Numeric(12, 2))
    min_lot_width_ft: Mapped[float | None] = mapped_column(Numeric(10, 2))
    max_height_ft: Mapped[float | None] = mapped_column(Numeric(10, 2))
    max_units: Mapped[int | None] = mapped_column(Integer)
    max_occupancy_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    front_setback_ft: Mapped[float | None] = mapped_column(Numeric(10, 2))
    side_setback_ft: Mapped[float | None] = mapped_column(Numeric(10, 2))
    rear_setback_ft: Mapped[float | None] = mapped_column(Numeric(10, 2))
    min_parking_spaces: Mapped[int | None] = mapped_column(Integer)
