from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision: str = "ee072d5de889"
down_revision: str | None = "d4e8b2f1a6c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_geospatial_table(
        "buyer_profile",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("market_code", sa.String(length=10), nullable=False),
        sa.Column("buyer_key", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("purchases_window", sa.Integer(), nullable=False),
        sa.Column("lot_purchases_window", sa.Integer(), nullable=False),
        sa.Column("last_purchase_at", sa.Date(), nullable=True),
        sa.Column("median_price", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("total_consideration", sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column("mailing_address", sa.String(length=255), nullable=True),
        sa.Column(
            "activity_centroid",
            Geometry(
                geometry_type="POINT",
                srid=0,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=True,
        ),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market_code", "buyer_key", name="uq_buyer_profile_market_key"),
    )
    op.create_geospatial_index(
        "idx_buyer_profile_activity_centroid",
        "buyer_profile",
        ["activity_centroid"],
        unique=False,
        postgresql_using="gist",
        postgresql_ops={},
    )
    op.create_index(
        op.f("ix_buyer_profile_market_code"), "buyer_profile", ["market_code"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_buyer_profile_market_code"), table_name="buyer_profile")
    op.drop_geospatial_index(
        "idx_buyer_profile_activity_centroid",
        table_name="buyer_profile",
        postgresql_using="gist",
        column_name="activity_centroid",
    )
    op.drop_geospatial_table("buyer_profile")
