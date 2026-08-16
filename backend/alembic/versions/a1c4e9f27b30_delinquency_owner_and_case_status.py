from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1c4e9f27b30"
down_revision: str | None = "f3a71c8d0e59"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tax_status", sa.Column("delinquency_owner", sa.String(length=255), nullable=True))
    op.add_column("tax_status", sa.Column("snapshot_period", sa.String(length=6), nullable=True))
    op.add_column("li_event", sa.Column("case_status", sa.String(length=60), nullable=True))
    op.add_column(
        "tax",
        sa.Column("delinquency_owner", sa.String(length=255), nullable=True),
        schema="staging",
    )
    op.add_column(
        "tax", sa.Column("snapshot_period", sa.String(length=6), nullable=True), schema="staging"
    )


def downgrade() -> None:
    op.drop_column("tax", "snapshot_period", schema="staging")
    op.drop_column("tax", "delinquency_owner", schema="staging")
    op.drop_column("li_event", "case_status")
    op.drop_column("tax_status", "snapshot_period")
    op.drop_column("tax_status", "delinquency_owner")
