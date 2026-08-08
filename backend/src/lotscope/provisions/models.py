from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base


class CodeProvision(Base):
    __tablename__ = "code_provision"
    __table_args__ = (
        Index("ix_code_provision_market_cite", "market_code", "cite"),
        Index("ix_code_provision_market_parent", "market_code", "parent"),
        Index("ix_code_provision_market_title_ordinal", "market_code", "title_number", "ordinal"),
    )

    market_code: Mapped[str] = mapped_column(
        String(10), ForeignKey("market.code"), primary_key=True
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cite: Mapped[str] = mapped_column(String(64), nullable=False)
    doc: Mapped[str] = mapped_column(String(16), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    title_number: Mapped[str] = mapped_column(String(8), nullable=False)
    parent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    path: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    heading: Mapped[str | None] = mapped_column(String(255), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    history: Mapped[str | None] = mapped_column(Text, nullable=True)
    refs: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    note_refs: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    table_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    source_file: Mapped[str] = mapped_column(String(120), nullable=False)
    source_version: Mapped[str] = mapped_column(String(40), nullable=False)
    loaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
