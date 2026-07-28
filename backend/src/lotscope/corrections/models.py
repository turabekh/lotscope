from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base
from lotscope.core.mixins import TimestampMixin


class ParcelCorrection(Base, TimestampMixin):
    __tablename__ = "parcel_correction"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    parcel_number: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    market_code: Mapped[str] = mapped_column(String(10), index=True, nullable=False)
    reported_by: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), index=True, nullable=False
    )

    section: Mapped[str] = mapped_column(String(40), nullable=False)
    field_name: Mapped[str | None] = mapped_column(String(60))

    verdict_version: Mapped[str | None] = mapped_column(String(10))
    verdict_computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    field_status: Mapped[str | None] = mapped_column(String(20))
    source_label: Mapped[str | None] = mapped_column(String(60))
    source_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    description: Mapped[str] = mapped_column(Text, nullable=False)
    attachment_ref: Mapped[str | None] = mapped_column(String(500))

    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="open")
    resolution: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), index=True
    )
