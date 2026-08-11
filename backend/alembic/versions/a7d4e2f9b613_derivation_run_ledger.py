from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7d4e2f9b613"
down_revision: str | None = "c8b3e5d197af"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "derivation_run",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=60), nullable=False),
        sa.Column("market_code", sa.String(length=10), nullable=False),
        sa.Column("title_number", sa.String(length=8), nullable=False),
        sa.Column("derivation_version", sa.String(length=16), nullable=False),
        sa.Column("source_version", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("provisions_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("documents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("table_documents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_continuations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_figures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_notes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_containers", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("folded_leaves", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pruned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reconciled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_derivation_run_source_title", "derivation_run", ["source", "title_number"])
    op.create_index("ix_derivation_run_run_id", "derivation_run", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_derivation_run_run_id", table_name="derivation_run")
    op.drop_index("ix_derivation_run_source_title", table_name="derivation_run")
    op.drop_table("derivation_run")
