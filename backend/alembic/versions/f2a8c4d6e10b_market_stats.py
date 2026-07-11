from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2a8c4d6e10b"
down_revision: str | None = "e5a1c8b0f2d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_stats",
        sa.Column("market_code", sa.String(length=10), nullable=False),
        sa.Column("parcel_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("geometry_pct", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("verdict_pct", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("vacant_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("vacant_with_comp_pct", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["market_code"], ["market.code"]),
        sa.PrimaryKeyConstraint("market_code"),
    )


def downgrade() -> None:
    op.drop_table("market_stats")
