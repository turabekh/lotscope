from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base
from lotscope.core.mixins import TimestampMixin


class SavedSearch(Base, TimestampMixin):
    __tablename__ = "saved_search"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    criteria: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    alerts_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SavedSearchMatch(Base):
    __tablename__ = "saved_search_match"

    saved_search_id: Mapped[int] = mapped_column(
        ForeignKey("saved_search.id", ondelete="CASCADE"), primary_key=True
    )
    parcel_number: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("parcel.parcel_number", ondelete="CASCADE"),
        primary_key=True,
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    notified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
