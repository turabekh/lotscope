from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base

ALERT_KINDS = (
    "sale_status",
    "new_violation",
    "new_delinquency",
    "neighbor_deed",
    "zba_filing",
)
ALERT_SCOPES = ("parcel", "area", "owned_neighbors")


class AgentAlert(Base):
    __tablename__ = "agent_alert"
    __table_args__ = (Index("ix_agent_alert_user_kind", "user_id", "kind"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    target: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    agent_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_run.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
