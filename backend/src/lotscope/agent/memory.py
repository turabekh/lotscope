"""What the Analyst remembers about one buyer between conversations.

A memory is something the buyer told us that no tool will ever return: where they will and
will not buy, what they lost at auction, what they decided and why. Anything a tool can look
up does not belong here — a stored copy of a fact that changes is a stale fact waiting to be
asserted.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base

MEMORY_KINDS = ("fact", "preference", "decision")

# How many memories reach the model. Enough to carry a working relationship, small enough
# that the buy box and the question still dominate the prompt.
MEMORY_WINDOW = 30


class AnalystMemory(Base):
    __tablename__ = "analyst_memory"
    __table_args__ = (Index("ix_analyst_memory_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_run.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
