from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5a8c2f4e137"
down_revision: str | None = "c3f7a1e9d260"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "li_event",
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("external_id", sa.String(length=60), nullable=False),
        sa.Column("ingest_run_id", sa.Integer(), nullable=False),
        sa.Column("parcel_number", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=True),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_unsafe", sa.Boolean(), nullable=True),
        sa.Column("is_imminently_dangerous", sa.Boolean(), nullable=True),
        sa.Column("source", sa.String(length=120), nullable=True),
        sa.PrimaryKeyConstraint("event_type", "external_id"),
        schema="staging",
    )


def downgrade() -> None:
    op.drop_table("li_event", schema="staging")
