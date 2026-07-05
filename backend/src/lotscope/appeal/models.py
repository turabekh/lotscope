from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base


class AppealPacketEntitlement(Base):
    __tablename__ = "appeal_packet"
    __table_args__ = (Index("ix_appeal_packet_user_parcel", "user_id", "parcel_number"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    parcel_number: Mapped[str] = mapped_column(
        String(40), ForeignKey("parcel.parcel_number", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    ref: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
