"""launch hardening: analyst spend ledger, error events, per-account ceilings, job duration

Revision ID: e3c8a2d5b71f
Revises: d2b7f1c93a48
Create Date: 2026-09-06

Hand-written: autogenerate emits destructive junk against this schema.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e3c8a2d5b71f"
down_revision = "d2b7f1c93a48"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analyst_usage",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=10), nullable=False, server_default="chat"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("usd_estimate", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("runs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "day", "source", name="uq_analyst_usage_user_day_source"),
    )
    op.create_index("ix_analyst_usage_user_id", "analyst_usage", ["user_id"])
    op.create_index("ix_analyst_usage_day", "analyst_usage", ["day"])

    op.create_table(
        "error_event",
        sa.Column("fingerprint", sa.String(length=200), primary_key=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("kind", sa.String(length=120), nullable=False),
        sa.Column("where", sa.String(length=200), nullable=False),
        sa.Column("sample", sa.Text(), nullable=True),
        sa.Column("context", postgresql.JSONB(), nullable=True),
        sa.Column("occurrences", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notified_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_error_event_last_seen_at", "error_event", ["last_seen_at"])

    op.add_column("app_user", sa.Column("analyst_daily_usd", sa.Numeric(8, 2), nullable=True))
    op.add_column("app_user", sa.Column("analyst_daily_runs", sa.Integer(), nullable=True))
    op.add_column("job_run", sa.Column("duration_ms", sa.Integer(), nullable=True))

    # Rows this deployment already has: a duration nobody recorded is better read from
    # the timestamps than left blank, and every one of them was closed by the process
    # that ran it, so the two figures mean the same thing.
    op.execute(
        "UPDATE job_run SET duration_ms = "
        "  round(extract(epoch FROM (finished_at - started_at)) * 1000) "
        "WHERE duration_ms IS NULL AND started_at IS NOT NULL AND finished_at IS NOT NULL "
        "  AND status <> 'interrupted'"
    )


def downgrade() -> None:
    op.drop_column("job_run", "duration_ms")
    op.drop_column("app_user", "analyst_daily_runs")
    op.drop_column("app_user", "analyst_daily_usd")
    op.drop_index("ix_error_event_last_seen_at", table_name="error_event")
    op.drop_table("error_event")
    op.drop_index("ix_analyst_usage_day", table_name="analyst_usage")
    op.drop_index("ix_analyst_usage_user_id", table_name="analyst_usage")
    op.drop_table("analyst_usage")
