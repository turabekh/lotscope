from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4e8a1f9d3b6"
down_revision: str | None = "b8d4f0a2c6e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "zoning_standard",
        sa.Column("lot_area_per_unit_sqft", sa.Numeric(12, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("zoning_standard", "lot_area_per_unit_sqft")
