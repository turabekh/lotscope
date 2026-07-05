from datetime import date

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import Boolean, Computed, Date, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base
from lotscope.core.mixins import IngestionMixin, TimestampMixin

OWNER_KEY_EXPRESSION = (
    "nullif(upper(btrim("
    "regexp_replace(regexp_replace(owner, '[.,#]', '', 'g'), '\\s+', ' ', 'g')"
    ")), '')"
)


class Parcel(Base, TimestampMixin, IngestionMixin):
    __tablename__ = "parcel"
    __table_args__ = (
        Index(
            "ix_parcel_address_trgm",
            "address",
            postgresql_using="gin",
            postgresql_ops={"address": "gin_trgm_ops"},
        ),
        Index(
            "ix_parcel_owner_trgm",
            "owner",
            postgresql_using="gin",
            postgresql_ops={"owner": "gin_trgm_ops"},
        ),
    )

    parcel_number: Mapped[str] = mapped_column(String(40), primary_key=True)
    market_code: Mapped[str] = mapped_column(
        String(10), ForeignKey("market.code"), nullable=False, server_default="phl", index=True
    )
    local_key: Mapped[str] = mapped_column(
        String(40),
        Computed("substring(parcel_number from strpos(parcel_number, ':') + 1)", persisted=True),
    )
    pwd_parcel_id: Mapped[str | None] = mapped_column(String(40), index=True)
    brt_number: Mapped[str | None] = mapped_column(String(40), index=True)

    address: Mapped[str | None] = mapped_column(String(255))
    zip_code: Mapped[str | None] = mapped_column(String(10))
    owner: Mapped[str | None] = mapped_column(String(255))
    owner_key: Mapped[str | None] = mapped_column(
        String(255), Computed(OWNER_KEY_EXPRESSION, persisted=True), index=True
    )
    mailing_address: Mapped[str | None] = mapped_column(String(255))

    land_use: Mapped[str | None] = mapped_column(String(120))
    category: Mapped[str | None] = mapped_column(String(120))
    base_zoning_code: Mapped[str | None] = mapped_column(String(20), index=True)

    market_value: Mapped[float | None] = mapped_column(Numeric(14, 2))
    land_value: Mapped[float | None] = mapped_column(Numeric(14, 2))
    improvement_value: Mapped[float | None] = mapped_column(Numeric(14, 2))
    exempt_land: Mapped[float | None] = mapped_column(Numeric(14, 2))
    exempt_building: Mapped[float | None] = mapped_column(Numeric(14, 2))
    assessment_year: Mapped[int | None]

    lot_area_sqft: Mapped[float | None] = mapped_column(Numeric(14, 2))
    frontage_ft: Mapped[float | None] = mapped_column(Numeric(10, 2))
    depth_ft: Mapped[float | None] = mapped_column(Numeric(10, 2))

    is_vacant: Mapped[bool | None] = mapped_column(Boolean)
    vacancy_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    is_city_owned: Mapped[bool | None] = mapped_column(Boolean)

    recorded_at: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)

    geom_local: Mapped[WKBElement | None] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=0, spatial_index=True)
    )
    geom_4326: Mapped[WKBElement | None] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=True)
    )
