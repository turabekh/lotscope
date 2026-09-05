from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base

_GRANT_IDEMPOTENCY_PREDICATE = text("reason <> 'skiptrace_burn' AND ref IS NOT NULL")


class SkipTraceResult(Base):
    __tablename__ = "skiptrace_result"

    owner_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    traced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
