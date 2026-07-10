from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d3b9f1c72a48"
down_revision: str | None = "b1d7e4a90c35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_run",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.String(length=120), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("market_code", sa.String(length=10), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="queued", nullable=False),
        sa.Column("arq_job_id", sa.String(length=120), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_count", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("triggered_by", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["triggered_by"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_run_job_id", "job_run", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_job_run_job_id", table_name="job_run")
    op.drop_table("job_run")
