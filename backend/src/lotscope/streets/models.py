from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base
from lotscope.core.mixins import IngestionMixin, TimestampMixin


class StreetCenterline(Base, TimestampMixin, IngestionMixin):
    __tablename__ = "street_centerline"
    __table_args__ = (UniqueConstraint("external_id", name="uq_street_centerline_external"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str | None] = mapped_column(String(60), index=True)
    street_name: Mapped[str | None] = mapped_column(String(120))
    street_class: Mapped[str | None] = mapped_column(String(40))

    market_code: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="phl", index=True
    )
    geom_local: Mapped[WKBElement | None] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=0, spatial_index=True)
    )
    geom_4326: Mapped[WKBElement | None] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=True)
    )
