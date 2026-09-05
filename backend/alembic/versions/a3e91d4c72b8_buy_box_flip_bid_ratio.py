from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3e91d4c72b8"
down_revision: str | None = "f7b3d81e60a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "buy_box",
        sa.Column("flip_bid_ratio", sa.Numeric(4, 3), nullable=False, server_default="0.700"),
    )


def downgrade() -> None:
    op.drop_column("buy_box", "flip_bid_ratio")
