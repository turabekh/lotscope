from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9fea8e83976d"
down_revision: str | None = "906c45d15071"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "dataset_freshness", sa.Column("market_code", sa.String(length=10), nullable=True)
    )
    op.execute("UPDATE dataset_freshness SET market_code = 'phl'")
    op.alter_column("dataset_freshness", "market_code", server_default="phl", nullable=False)
    op.drop_constraint("dataset_freshness_pkey", "dataset_freshness", type_="primary")
    op.create_primary_key(
        "dataset_freshness_pkey", "dataset_freshness", ["market_code", "dataset"]
    )
    op.create_foreign_key(
        "dataset_freshness_market_code_fkey",
        "dataset_freshness",
        "market",
        ["market_code"],
        ["code"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "dataset_freshness_market_code_fkey", "dataset_freshness", type_="foreignkey"
    )
    op.drop_constraint("dataset_freshness_pkey", "dataset_freshness", type_="primary")
    op.create_primary_key("dataset_freshness_pkey", "dataset_freshness", ["dataset"])
    op.drop_column("dataset_freshness", "market_code")
