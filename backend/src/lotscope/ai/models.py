from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base
from lotscope.core.mixins import TimestampMixin

EMBEDDING_DIMENSIONS = 1024


class Document(Base, TimestampMixin):
    __tablename__ = "document"
    __table_args__ = (
        Index(
            "ix_document_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(60), index=True)
    section: Mapped[str | None] = mapped_column(String(120), index=True)
    title: Mapped[str | None] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    doc_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS))


class DerivationRun(Base):
    __tablename__ = "derivation_run"
    __table_args__ = (
        Index("ix_derivation_run_source_title", "source", "title_number"),
        Index("ix_derivation_run_run_id", "run_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36))
    source: Mapped[str] = mapped_column(String(60))
    market_code: Mapped[str] = mapped_column(String(10))
    title_number: Mapped[str] = mapped_column(String(8))
    derivation_version: Mapped[str] = mapped_column(String(16))
    source_version: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16))
    error: Mapped[str | None] = mapped_column(Text)
    provisions_seen: Mapped[int] = mapped_column(Integer, default=0)
    documents: Mapped[int] = mapped_column(Integer, default=0)
    table_documents: Mapped[int] = mapped_column(Integer, default=0)
    skipped_continuations: Mapped[int] = mapped_column(Integer, default=0)
    skipped_figures: Mapped[int] = mapped_column(Integer, default=0)
    skipped_notes: Mapped[int] = mapped_column(Integer, default=0)
    skipped_containers: Mapped[int] = mapped_column(Integer, default=0)
    folded_leaves: Mapped[int] = mapped_column(Integer, default=0)
    pruned: Mapped[int] = mapped_column(Integer, default=0)
    reconciled: Mapped[bool] = mapped_column(default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
