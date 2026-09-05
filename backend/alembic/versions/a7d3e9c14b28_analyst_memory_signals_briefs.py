"""analyst memory, signals and briefs

Revision ID: a7d3e9c14b28
Revises: f4c81a6b930e
Create Date: 2026-09-05

Hand-written: autogenerate emits destructive junk against this schema.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a7d3e9c14b28"
down_revision = "f4c81a6b930e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analyst_memory",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source_run_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_run_id"], ["agent_run.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analyst_memory_user_id", "analyst_memory", ["user_id"])
    op.create_index("ix_analyst_memory_user_created", "analyst_memory", ["user_id", "created_at"])

    op.create_table(
        "analyst_signal",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("signal_key", sa.String(length=200), nullable=False),
        sa.Column("signal_date", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("parcel_number", sa.String(length=40), nullable=True),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column(
            "detail", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("source", sa.String(length=60), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_table", sa.String(length=60), nullable=False),
        sa.Column("source_row_id", sa.String(length=80), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "signal_key", name="uq_analyst_signal_user_key"),
    )
    op.create_index("ix_analyst_signal_user_id", "analyst_signal", ["user_id"])
    op.create_index("ix_analyst_signal_parcel_number", "analyst_signal", ["parcel_number"])
    op.create_index("ix_analyst_signal_user_day", "analyst_signal", ["user_id", "signal_date"])

    op.create_table(
        "analyst_brief",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("brief_date", sa.Date(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("signal_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("emailed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("run_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_run.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "brief_date", name="uq_analyst_brief_user_day"),
    )
    op.create_index("ix_analyst_brief_user_id", "analyst_brief", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_analyst_brief_user_id", table_name="analyst_brief")
    op.drop_table("analyst_brief")
    op.drop_index("ix_analyst_signal_user_day", table_name="analyst_signal")
    op.drop_index("ix_analyst_signal_parcel_number", table_name="analyst_signal")
    op.drop_index("ix_analyst_signal_user_id", table_name="analyst_signal")
    op.drop_table("analyst_signal")
    op.drop_index("ix_analyst_memory_user_created", table_name="analyst_memory")
    op.drop_index("ix_analyst_memory_user_id", table_name="analyst_memory")
    op.drop_table("analyst_memory")
