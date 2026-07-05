from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1219f3299db0"
down_revision: str | None = "ea5bd26236ef"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "zoning_standard", sa.Column("market_code", sa.String(length=10), nullable=True)
    )
    op.execute("UPDATE zoning_standard SET market_code = 'phl'")
    op.alter_column("zoning_standard", "market_code", server_default="phl", nullable=False)
    op.create_index(
        "ix_zoning_standard_market_code", "zoning_standard", ["market_code"]
    )
    op.create_foreign_key(
        "zoning_standard_market_code_fkey",
        "zoning_standard",
        "market",
        ["market_code"],
        ["code"],
    )
    op.drop_constraint(
        "uq_zoning_standard_code_version", "zoning_standard", type_="unique"
    )
    op.create_unique_constraint(
        "uq_zoning_standard_market_code_version",
        "zoning_standard",
        ["market_code", "code", "code_version"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_zoning_standard_market_code_version", "zoning_standard", type_="unique"
    )
    op.create_unique_constraint(
        "uq_zoning_standard_code_version", "zoning_standard", ["code", "code_version"]
    )
    op.drop_constraint(
        "zoning_standard_market_code_fkey", "zoning_standard", type_="foreignkey"
    )
    op.drop_index("ix_zoning_standard_market_code", table_name="zoning_standard")
    op.drop_column("zoning_standard", "market_code")
