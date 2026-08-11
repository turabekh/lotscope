from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3a71c8d0e59"
down_revision: str | Sequence[str] | None = "e5b1c93a7d24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "parcel_overlay",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("market_code", sa.String(length=10), server_default="phl", nullable=False),
        sa.Column("parcel_number", sa.String(length=40), nullable=False),
        sa.Column("overlay_id", sa.Integer(), nullable=False),
        sa.Column("overlay_code", sa.String(length=30), nullable=True),
        sa.Column("overlay_name", sa.String(length=255), nullable=True),
        sa.Column("code_section", sa.String(length=60), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["market_code"], ["market.code"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "market_code", "parcel_number", "overlay_id", name="uq_parcel_overlay_membership"
        ),
    )
    op.create_index("ix_parcel_overlay_market_code", "parcel_overlay", ["market_code"])
    op.create_index("ix_parcel_overlay_parcel_number", "parcel_overlay", ["parcel_number"])
    op.create_index("ix_parcel_overlay_code_section", "parcel_overlay", ["code_section"])
    op.create_index(
        "ix_parcel_overlay_lookup", "parcel_overlay", ["market_code", "parcel_number"]
    )


def downgrade() -> None:
    op.drop_index("ix_parcel_overlay_lookup", table_name="parcel_overlay")
    op.drop_index("ix_parcel_overlay_code_section", table_name="parcel_overlay")
    op.drop_index("ix_parcel_overlay_parcel_number", table_name="parcel_overlay")
    op.drop_index("ix_parcel_overlay_market_code", table_name="parcel_overlay")
    op.drop_table("parcel_overlay")
