from datetime import date

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import Date, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base
from lotscope.core.mixins import IngestionMixin, TimestampMixin


class HistoricDistrict(Base, TimestampMixin, IngestionMixin):
    __tablename__ = "historic_district"
    __table_args__ = (UniqueConstraint("external_id", name="uq_historic_district_external"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str | None] = mapped_column(String(60), index=True)
    name: Mapped[str | None] = mapped_column(String(160), index=True)
    designated_date: Mapped[date | None] = mapped_column(Date)

    geom_local: Mapped[WKBElement | None] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=0, spatial_index=True)
    )
    geom_4326: Mapped[WKBElement | None] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=True)
    )
