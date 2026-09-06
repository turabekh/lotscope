from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base
from lotscope.core.mixins import TimestampMixin


class DiligenceRun(Base, TimestampMixin):
    """One buyer's diligence on one parcel.

    Kept because the report is a paid artefact: the buyer comes back to it, and the
    checklist they bought is the one they must be able to download again, not a fresh
    read that might now say something else.
    """

    __tablename__ = "diligence_run"
    __table_args__ = (Index("ix_diligence_run_user_parcel", "user_id", "parcel_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    parcel_number: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    pdf_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
