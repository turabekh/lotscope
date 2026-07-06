from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5c9b2d1a473"
down_revision: str | None = "d4f1a8c2e9b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("parcel", sa.Column("condemned_status", sa.String(length=30), nullable=True))


def downgrade() -> None:
    op.drop_column("parcel", "condemned_status")
