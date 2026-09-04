from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1c7e4f90b62"
down_revision: str | Sequence[str] | None = "e6a91c47f2d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("repository_listing")
    op.drop_table("market_gate_item")
    op.drop_constraint("buyer_profile_market_code_fkey", "buyer_profile", type_="foreignkey")
    op.drop_constraint("code_provision_market_code_fkey", "code_provision", type_="foreignkey")
    op.drop_constraint(
        "dataset_freshness_market_code_fkey", "dataset_freshness", type_="foreignkey"
    )
    op.drop_constraint("flood_zone_market_code_fkey", "flood_zone", type_="foreignkey")
    op.drop_constraint(
        "historic_district_market_code_fkey", "historic_district", type_="foreignkey"
    )
    op.drop_constraint("market_stats_market_code_fkey", "market_stats", type_="foreignkey")
    op.drop_constraint("neighborhood_market_code_fkey", "neighborhood", type_="foreignkey")
    op.drop_constraint("overlay_standard_market_code_fkey", "overlay_standard", type_="foreignkey")
    op.drop_constraint("parcel_market_code_fkey", "parcel", type_="foreignkey")
    op.drop_constraint("parcel_overlay_market_code_fkey", "parcel_overlay", type_="foreignkey")
    op.drop_constraint("rco_market_code_fkey", "rco", type_="foreignkey")
    op.drop_constraint("saved_search_market_code_fkey", "saved_search", type_="foreignkey")
    op.drop_constraint(
        "street_centerline_market_code_fkey", "street_centerline", type_="foreignkey"
    )
    op.drop_constraint("zoning_district_market_code_fkey", "zoning_district", type_="foreignkey")
    op.drop_constraint("zoning_overlay_market_code_fkey", "zoning_overlay", type_="foreignkey")
    op.drop_constraint("zoning_standard_market_code_fkey", "zoning_standard", type_="foreignkey")


def downgrade() -> None:
    op.create_table(
        "market_gate_item",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("market_code", sa.String(length=10), nullable=False),
        sa.Column("gate_type", sa.String(length=20), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("satisfied", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("qualifier", sa.String(length=80), nullable=True),
        sa.Column("threshold", sa.String(length=80), nullable=True),
        sa.Column("measured", sa.Text(), nullable=True),
        sa.Column("owner", sa.String(length=80), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("spec_ref", sa.String(length=40), nullable=True),
        sa.Column("as_of", sa.Date(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "market_code", "gate_type", "ordinal", name="uq_market_gate_item_market_type_ordinal"
        ),
    )
    op.create_index(
        "ix_market_gate_item_market_code", "market_gate_item", ["market_code"], unique=False
    )
    op.create_table(
        "repository_listing",
        sa.Column("parcel_number", sa.String(length=40), nullable=False),
        sa.Column("city_status", sa.String(length=40), nullable=True),
        sa.Column("bid_pending", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("list_as_of", sa.Date(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("external_id", sa.String(length=60), nullable=True),
        sa.Column("source", sa.String(length=60), nullable=True),
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
        sa.ForeignKeyConstraint(["parcel_number"], ["parcel.parcel_number"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("parcel_number"),
    )
    op.create_foreign_key(
        "buyer_profile_market_code_fkey", "buyer_profile", "market", ["market_code"], ["code"]
    )
    op.create_foreign_key(
        "code_provision_market_code_fkey", "code_provision", "market", ["market_code"], ["code"]
    )
    op.create_foreign_key(
        "dataset_freshness_market_code_fkey",
        "dataset_freshness",
        "market",
        ["market_code"],
        ["code"],
    )
    op.create_foreign_key(
        "flood_zone_market_code_fkey", "flood_zone", "market", ["market_code"], ["code"]
    )
    op.create_foreign_key(
        "historic_district_market_code_fkey",
        "historic_district",
        "market",
        ["market_code"],
        ["code"],
    )
    op.create_foreign_key(
        "market_stats_market_code_fkey", "market_stats", "market", ["market_code"], ["code"]
    )
    op.create_foreign_key(
        "neighborhood_market_code_fkey", "neighborhood", "market", ["market_code"], ["code"]
    )
    op.create_foreign_key(
        "overlay_standard_market_code_fkey", "overlay_standard", "market", ["market_code"], ["code"]
    )
    op.create_foreign_key("parcel_market_code_fkey", "parcel", "market", ["market_code"], ["code"])
    op.create_foreign_key(
        "parcel_overlay_market_code_fkey", "parcel_overlay", "market", ["market_code"], ["code"]
    )
    op.create_foreign_key("rco_market_code_fkey", "rco", "market", ["market_code"], ["code"])
    op.create_foreign_key(
        "saved_search_market_code_fkey", "saved_search", "market", ["market_code"], ["code"]
    )
    op.create_foreign_key(
        "street_centerline_market_code_fkey",
        "street_centerline",
        "market",
        ["market_code"],
        ["code"],
    )
    op.create_foreign_key(
        "zoning_district_market_code_fkey", "zoning_district", "market", ["market_code"], ["code"]
    )
    op.create_foreign_key(
        "zoning_overlay_market_code_fkey", "zoning_overlay", "market", ["market_code"], ["code"]
    )
    op.create_foreign_key(
        "zoning_standard_market_code_fkey", "zoning_standard", "market", ["market_code"], ["code"]
    )
