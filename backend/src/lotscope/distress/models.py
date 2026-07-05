from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base
from lotscope.core.mixins import ProvenanceMixin, TimestampMixin


class ParcelDistress(Base, TimestampMixin, ProvenanceMixin):
    __tablename__ = "parcel_distress"

    parcel_number: Mapped[str] = mapped_column(
        String(40),
        ForeignKey("parcel.parcel_number", ondelete="CASCADE"),
        primary_key=True,
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False, server_default="v2")
