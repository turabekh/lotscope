from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5f8a2c31b74"
down_revision: str | None = "c3e7b1f92d04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "parcel_distress",
        sa.Column("debt_counts", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("parcel_distress", "debt_counts")
