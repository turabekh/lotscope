from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "a2d7f4c8e1b5"
down_revision: str | None = "f1c5e9b3a7d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("saved_parcel", sa.Column("snapshot", JSONB(), nullable=True))
    op.add_column(
        "saved_parcel", sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("saved_parcel", "snapshot_at")
    op.drop_column("saved_parcel", "snapshot")
