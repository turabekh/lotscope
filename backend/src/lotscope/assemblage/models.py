from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base
from lotscope.core.mixins import ProvenanceMixin, TimestampMixin


class ParcelAssemblage(Base, TimestampMixin, ProvenanceMixin):
    __tablename__ = "parcel_assemblage"

    parcel_number: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("parcel.parcel_number", ondelete="CASCADE"),
        primary_key=True,
    )
    potential: Mapped[str] = mapped_column(String(20), nullable=False)
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    combined_lot_area_sqft: Mapped[float | None] = mapped_column(Numeric(14, 2))
    by_right_units_current: Mapped[int | None] = mapped_column(Integer)
    by_right_units_combined: Mapped[int | None] = mapped_column(Integer)
    unit_unlock: Mapped[int | None] = mapped_column(Integer, index=True)
    base_zoning_code: Mapped[str | None] = mapped_column(String(20), index=True)
    neighborhood: Mapped[str | None] = mapped_column(String(120), index=True)
