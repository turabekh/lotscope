from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base
from lotscope.core.mixins import ProvenanceMixin, TimestampMixin


class ParcelVerdict(Base, TimestampMixin, ProvenanceMixin):
    __tablename__ = "parcel_verdict"

    parcel_number: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("parcel.parcel_number", ondelete="CASCADE"),
        primary_key=True,
    )
    verdict_version: Mapped[str] = mapped_column(String(40), nullable=False)

    buildability_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    opportunity_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    summary: Mapped[str | None] = mapped_column(Text)

    can_build_by_right: Mapped[bool | None] = mapped_column(Boolean)
    by_right_units: Mapped[int | None] = mapped_column(Integer)
    max_height_ft: Mapped[float | None] = mapped_column(Numeric(10, 2))
    needs_variance: Mapped[bool | None] = mapped_column(Boolean)
    buildable_area_sqft: Mapped[float | None] = mapped_column(Numeric(14, 2))

    value_estimate_low: Mapped[float | None] = mapped_column(Numeric(14, 2))
    value_estimate_high: Mapped[float | None] = mapped_column(Numeric(14, 2))
    value_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    assessment_market_gap: Mapped[float | None] = mapped_column(Numeric(14, 2))

    risk_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    risk_flags: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
