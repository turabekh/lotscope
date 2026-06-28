from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8e2f5a1d3b7"
down_revision: str | None = "b7c1d4e9a2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "parcel_verdict",
        "est_margin",
        type_=sa.Numeric(14, 4),
        existing_type=sa.Numeric(6, 4),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "parcel_verdict",
        "est_margin",
        type_=sa.Numeric(6, 4),
        existing_type=sa.Numeric(14, 4),
        existing_nullable=True,
    )
