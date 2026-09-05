from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base


class AgentConversation(Base):
    __tablename__ = "agent_conversation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AgentRun(Base):
    __tablename__ = "agent_run"
    __table_args__ = (Index("ix_agent_run_conversation_created", "conversation_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("agent_conversation.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="running")
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    stop_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    tool_calls: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentStep(Base):
    __tablename__ = "agent_step"
    __table_args__ = (Index("ix_agent_step_run_seq", "run_id", "sequence"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("agent_run.id", ondelete="CASCADE"), index=True, nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    tool_input: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    envelope: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
