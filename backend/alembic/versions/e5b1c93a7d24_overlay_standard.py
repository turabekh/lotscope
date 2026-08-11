from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5b1c93a7d24"
down_revision: str | Sequence[str] | None = "a7d4e2f9b613"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "overlay_standard",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "market_code", sa.String(length=10), server_default="phl", nullable=False
        ),
        sa.Column("code_section", sa.String(length=60), nullable=False),
        sa.Column("overlay_code", sa.String(length=30), nullable=False),
        sa.Column("district_code", sa.String(length=20), nullable=False),
        sa.Column("field", sa.String(length=40), nullable=False),
        sa.Column("value", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("citation", sa.String(length=60), nullable=False),
        sa.Column("code_version", sa.String(length=40), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["market_code"], ["market.code"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "market_code",
            "code_section",
            "district_code",
            "field",
            "code_version",
            name="uq_overlay_standard_scope",
        ),
    )
    op.create_index(
        "ix_overlay_standard_market_code", "overlay_standard", ["market_code"], unique=False
    )
    op.create_index(
        "ix_overlay_standard_code_section", "overlay_standard", ["code_section"], unique=False
    )
    op.create_index(
        "ix_overlay_standard_district_code", "overlay_standard", ["district_code"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_overlay_standard_district_code", table_name="overlay_standard")
    op.drop_index("ix_overlay_standard_code_section", table_name="overlay_standard")
    op.drop_index("ix_overlay_standard_market_code", table_name="overlay_standard")
    op.drop_table("overlay_standard")
