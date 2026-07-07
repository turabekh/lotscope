from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7c3e9f1a2b84"
down_revision: str | None = "e5c9b2d1a473"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "parcel_distress", sa.Column("profile_id", sa.String(length=40), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("parcel_distress", "profile_id")
