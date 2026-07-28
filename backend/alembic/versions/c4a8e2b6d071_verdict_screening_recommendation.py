from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4a8e2b6d071"
down_revision: str | None = "b7e1d3f5c942"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("parcel_verdict", sa.Column("recommendation", sa.String(length=40), nullable=True))
    op.add_column("parcel_verdict", sa.Column("recommendation_reason", sa.Text(), nullable=True))
    op.add_column(
        "parcel_verdict", sa.Column("decision_version", sa.String(length=10), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("parcel_verdict", "decision_version")
    op.drop_column("parcel_verdict", "recommendation_reason")
    op.drop_column("parcel_verdict", "recommendation")
