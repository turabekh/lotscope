from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2d5f0a83c17"
down_revision: str | None = "a1c4e9f27b30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("dataset_freshness", sa.Column("data_vintage", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("dataset_freshness", "data_vintage")
