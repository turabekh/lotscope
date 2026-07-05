from typing import Any

from sqlalchemy import Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base
from lotscope.core.mixins import TimestampMixin


class Market(Base, TimestampMixin):
    __tablename__ = "market"
    __table_args__ = (UniqueConstraint("url_slug", name="uq_market_url_slug"),)

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str | None] = mapped_column(String(2))
    url_slug: Mapped[str] = mapped_column(String(60), nullable=False)
    local_srid: Mapped[int] = mapped_column(Integer, nullable=False)
    map_center: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    map_bounds: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    default_zoom: Mapped[float] = mapped_column(Numeric(4, 1), nullable=False)
    timezone: Mapped[str] = mapped_column(String(40), nullable=False)
    recorder_url_template: Mapped[str | None] = mapped_column(Text)
    deal_assumption_overrides: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    coverage_note: Mapped[str | None] = mapped_column(Text)
    launch_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="live")
