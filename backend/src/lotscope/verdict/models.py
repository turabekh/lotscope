from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base
from lotscope.core.mixins import ProvenanceMixin, TimestampMixin


class ParcelScreen(Base, TimestampMixin, ProvenanceMixin):
    """The nightly screening index over vacant land.

    Not a verdict: it exists so that one query can rank 38,000 lots or pre-filter a buy
    box, which computing each one on read cannot do. Nothing here is ever handed to a
    user as the read on a lot — that comes from get_verdict, which computes it. Every
    row is replaced by the nightly rebuild, and computed_at says when.
    """

    __tablename__ = "parcel_screen"

    parcel_number: Mapped[str] = mapped_column(
        String(40),
        ForeignKey("parcel.parcel_number", ondelete="CASCADE"),
        primary_key=True,
    )

    opportunity_score: Mapped[float | None] = mapped_column(Numeric(5, 2), index=True)
    deal_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    max_allowable_offer: Mapped[float | None] = mapped_column(Numeric(14, 2))
    est_margin: Mapped[float | None] = mapped_column(Numeric(14, 4))
    risk_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    by_right_units: Mapped[int | None] = mapped_column(Integer)
    can_build_by_right: Mapped[bool | None] = mapped_column(Boolean)
    is_underpriced: Mapped[bool | None] = mapped_column(Boolean)
