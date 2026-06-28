from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7c1d4e9a2f3"
down_revision: str | None = "d9b2e5f7c3a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("parcel_verdict", sa.Column("arv", sa.Numeric(14, 2), nullable=True))
    op.add_column("parcel_verdict", sa.Column("est_profit", sa.Numeric(14, 2), nullable=True))
    op.add_column("parcel_verdict", sa.Column("est_margin", sa.Numeric(6, 4), nullable=True))
    op.add_column(
        "parcel_verdict", sa.Column("max_allowable_offer", sa.Numeric(14, 2), nullable=True)
    )
    op.add_column("parcel_verdict", sa.Column("deal_score", sa.Numeric(5, 2), nullable=True))
    op.add_column("parcel_verdict", sa.Column("is_underpriced", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("parcel_verdict", "is_underpriced")
    op.drop_column("parcel_verdict", "deal_score")
    op.drop_column("parcel_verdict", "max_allowable_offer")
    op.drop_column("parcel_verdict", "est_margin")
    op.drop_column("parcel_verdict", "est_profit")
    op.drop_column("parcel_verdict", "arv")
