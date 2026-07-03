from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base

_GRANT_IDEMPOTENCY_PREDICATE = text("reason <> 'skiptrace_burn' AND ref IS NOT NULL")

REASON_PACK_PURCHASE = "pack_purchase"
REASON_SKIPTRACE_BURN = "skiptrace_burn"
REASON_INVESTOR_GRANT = "investor_grant"
REASON_APPEAL_PACKET_GRANT = "appeal_packet_grant"
REASON_APPEAL_PACKET_BURN = "appeal_packet_burn"
REASON_REFUND = "refund"

SKIPTRACE_REASONS = (
    REASON_PACK_PURCHASE,
    REASON_SKIPTRACE_BURN,
    REASON_INVESTOR_GRANT,
    REASON_REFUND,
)
APPEAL_PACKET_REASONS = (REASON_APPEAL_PACKET_GRANT, REASON_APPEAL_PACKET_BURN)


class CreditLedgerEntry(Base):
    __tablename__ = "credit_ledger"
    __table_args__ = (
        Index(
            "uq_credit_ledger_grant_ref",
            "user_id",
            "reason",
            "ref",
            unique=True,
            postgresql_where=_GRANT_IDEMPOTENCY_PREDICATE,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(40), nullable=False)
    ref: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SkipTraceResult(Base):
    __tablename__ = "skiptrace_result"

    owner_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    traced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
