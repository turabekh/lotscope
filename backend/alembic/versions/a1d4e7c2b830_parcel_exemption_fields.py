from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1d4e7c2b830"
down_revision: str | None = "f8c3d1a7b62e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("parcel", sa.Column("exempt_land", sa.Numeric(precision=14, scale=2), nullable=True))
    op.add_column(
        "parcel", sa.Column("exempt_building", sa.Numeric(precision=14, scale=2), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("parcel", "exempt_building")
    op.drop_column("parcel", "exempt_land")
