from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision: str = "e6b2f9a4c81d"
down_revision: str | None = "d4a7e2c8f1b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_geospatial_table(
        "street_centerline",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_id", sa.String(length=60), nullable=True),
        sa.Column("street_name", sa.String(length=120), nullable=True),
        sa.Column("street_class", sa.String(length=40), nullable=True),
        sa.Column(
            "geom_2272",
            Geometry(
                srid=2272,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=True,
        ),
        sa.Column(
            "geom_4326",
            Geometry(
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("source", sa.String(length=120), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id", name="uq_street_centerline_external"),
    )
    op.create_geospatial_index(
        "idx_street_centerline_geom_2272",
        "street_centerline",
        ["geom_2272"],
        unique=False,
        postgresql_using="gist",
        postgresql_ops={},
    )
    op.create_geospatial_index(
        "idx_street_centerline_geom_4326",
        "street_centerline",
        ["geom_4326"],
        unique=False,
        postgresql_using="gist",
        postgresql_ops={},
    )
    op.create_index(
        op.f("ix_street_centerline_external_id"),
        "street_centerline",
        ["external_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_street_centerline_external_id"), table_name="street_centerline")
    op.drop_geospatial_index(
        "idx_street_centerline_geom_4326",
        table_name="street_centerline",
        postgresql_using="gist",
        column_name="geom_4326",
    )
    op.drop_geospatial_index(
        "idx_street_centerline_geom_2272",
        table_name="street_centerline",
        postgresql_using="gist",
        column_name="geom_2272",
    )
    op.drop_geospatial_table("street_centerline")
