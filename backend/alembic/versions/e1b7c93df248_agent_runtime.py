from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e1b7c93df248"
down_revision: str | None = "d9e2b71fa640"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_conversation",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_conversation_user_id", "agent_conversation", ["user_id"])

    op.create_table(
        "agent_run",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("stop_reason", sa.String(40), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tool_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["agent_conversation.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed', 'cancelled')", name="ck_agent_run_status"
        ),
    )
    op.create_index("ix_agent_run_conversation_id", "agent_run", ["conversation_id"])
    op.create_index("ix_agent_run_user_id", "agent_run", ["user_id"])
    op.create_index(
        "ix_agent_run_conversation_created", "agent_run", ["conversation_id", "created_at"]
    )

    op.create_table(
        "agent_step",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("tool_name", sa.String(80), nullable=True),
        sa.Column("tool_input", postgresql.JSONB(), nullable=True),
        sa.Column("envelope", postgresql.JSONB(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["run_id"], ["agent_run.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_step_run_id", "agent_step", ["run_id"])
    op.create_index("ix_agent_step_run_seq", "agent_step", ["run_id", "sequence"])


def downgrade() -> None:
    op.drop_index("ix_agent_step_run_seq", table_name="agent_step")
    op.drop_index("ix_agent_step_run_id", table_name="agent_step")
    op.drop_table("agent_step")
    op.drop_index("ix_agent_run_conversation_created", table_name="agent_run")
    op.drop_index("ix_agent_run_user_id", table_name="agent_run")
    op.drop_index("ix_agent_run_conversation_id", table_name="agent_run")
    op.drop_table("agent_run")
    op.drop_index("ix_agent_conversation_user_id", table_name="agent_conversation")
    op.drop_table("agent_conversation")
