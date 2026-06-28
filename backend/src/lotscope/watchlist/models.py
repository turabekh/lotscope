from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base
from lotscope.core.mixins import TimestampMixin


class SavedParcel(Base, TimestampMixin):
    __tablename__ = "saved_parcel"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    parcel_number: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("parcel.parcel_number", ondelete="CASCADE"),
        primary_key=True,
    )
    tags: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    note: Mapped[str | None] = mapped_column(Text)
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    snapshot_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
