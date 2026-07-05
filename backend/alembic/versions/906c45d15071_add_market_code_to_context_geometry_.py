from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "906c45d15071"
down_revision: str | None = "90713605d09d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONTEXT_TABLES = (
    "zoning_district",
    "zoning_overlay",
    "rco",
    "flood_zone",
    "historic_district",
    "neighborhood",
    "street_centerline",
)


def upgrade() -> None:
    for table in _CONTEXT_TABLES:
        op.add_column(table, sa.Column("market_code", sa.String(length=10), nullable=True))
        op.execute(f"UPDATE {table} SET market_code = 'phl'")
        op.alter_column(table, "market_code", server_default="phl", nullable=False)
        op.create_index(f"ix_{table}_market_code", table, ["market_code"])
        op.create_foreign_key(
            f"{table}_market_code_fkey", table, "market", ["market_code"], ["code"]
        )


def downgrade() -> None:
    for table in _CONTEXT_TABLES:
        op.drop_constraint(f"{table}_market_code_fkey", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_market_code", table_name=table)
        op.drop_column(table, "market_code")
