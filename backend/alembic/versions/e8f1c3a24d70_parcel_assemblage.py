from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e8f1c3a24d70"
down_revision: str | None = "d7a2f4b19c63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "parcel_assemblage",
        sa.Column("parcel_number", sa.String(length=20), nullable=False),
        sa.Column("potential", sa.String(length=20), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("combined_lot_area_sqft", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("by_right_units_current", sa.Integer(), nullable=True),
        sa.Column("by_right_units_combined", sa.Integer(), nullable=True),
        sa.Column("unit_unlock", sa.Integer(), nullable=True),
        sa.Column("base_zoning_code", sa.String(length=20), nullable=True),
        sa.Column("neighborhood", sa.String(length=120), nullable=True),
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
        sa.Column(
            "sources",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["parcel_number"], ["parcel.parcel_number"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("parcel_number"),
    )
    op.create_index(
        op.f("ix_parcel_assemblage_unit_unlock"), "parcel_assemblage", ["unit_unlock"], unique=False
    )
    op.create_index(
        op.f("ix_parcel_assemblage_base_zoning_code"),
        "parcel_assemblage",
        ["base_zoning_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_parcel_assemblage_neighborhood"),
        "parcel_assemblage",
        ["neighborhood"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_parcel_assemblage_neighborhood"), table_name="parcel_assemblage")
    op.drop_index(op.f("ix_parcel_assemblage_base_zoning_code"), table_name="parcel_assemblage")
    op.drop_index(op.f("ix_parcel_assemblage_unit_unlock"), table_name="parcel_assemblage")
    op.drop_table("parcel_assemblage")
