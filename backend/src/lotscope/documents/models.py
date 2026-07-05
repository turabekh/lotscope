from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base
from lotscope.core.mixins import TimestampMixin


class DeedDocument(Base, TimestampMixin):
    __tablename__ = "deed_document"
    __table_args__ = (UniqueConstraint("external_id", name="uq_deed_document_external"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parcel_number: Mapped[str] = mapped_column(
        String(40), ForeignKey("parcel.parcel_number", ondelete="CASCADE"), index=True
    )
    external_id: Mapped[str | None] = mapped_column(String(80), index=True)
    document_type: Mapped[str | None] = mapped_column(String(80))
    recording_date: Mapped[date | None] = mapped_column(Date)
    blob_key: Mapped[str | None] = mapped_column(String(255))
    ocr_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    source: Mapped[str | None] = mapped_column(String(120))


class DeedRestriction(Base, TimestampMixin):
    __tablename__ = "deed_restriction"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deed_document_id: Mapped[int] = mapped_column(
        ForeignKey("deed_document.id", ondelete="CASCADE"), index=True
    )
    parcel_number: Mapped[str] = mapped_column(
        String(40), ForeignKey("parcel.parcel_number", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    citation: Mapped[str | None] = mapped_column(String(255))
    confidence: Mapped[str] = mapped_column(String(10), nullable=False)
