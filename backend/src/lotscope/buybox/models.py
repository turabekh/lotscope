from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base
from lotscope.core.mixins import TimestampMixin


class BuyBox(Base, TimestampMixin):
    __tablename__ = "buy_box"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    areas: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    max_bid: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    target_use: Mapped[str] = mapped_column(String(8), nullable=False, server_default="build")
    min_lot_sqft: Mapped[int | None] = mapped_column(Integer, nullable=True)
    zoning_codes: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    exclude_city_neighbor: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    exclude_open_violations: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    exclude_historic: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    exclude_flood: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    assumptions: Mapped[dict[str, float]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    owned_parcels: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
