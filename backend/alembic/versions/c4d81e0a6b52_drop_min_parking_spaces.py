from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4d81e0a6b52"
down_revision: str | None = "a7f2c91b83de"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("zoning_standard", "min_parking_spaces")


def downgrade() -> None:
    op.add_column("zoning_standard", sa.Column("min_parking_spaces", sa.Integer(), nullable=True))
