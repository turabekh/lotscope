from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d6f2b9c4a8e1"
down_revision: str | None = "c4e8a1f9d3b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "zoning_standard",
        sa.Column("max_floor_area_ratio_pct", sa.Numeric(8, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("zoning_standard", "max_floor_area_ratio_pct")
