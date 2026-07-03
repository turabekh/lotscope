from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4e9a17b2d58"
down_revision: str | None = "b8d3f1a6c920"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "parcel_distress",
        sa.Column("version", sa.String(length=20), nullable=False, server_default="v2"),
    )


def downgrade() -> None:
    op.drop_column("parcel_distress", "version")
