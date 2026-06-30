from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision: str = "f8c3d1a7b62e"
down_revision: str | None = "e6b2f9a4c81d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_geospatial_table(
        "historic_district",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_id", sa.String(length=60), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=True),
        sa.Column("designated_date", sa.Date(), nullable=True),
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
        sa.UniqueConstraint("external_id", name="uq_historic_district_external"),
    )
    op.create_geospatial_index(
        "idx_historic_district_geom_2272",
        "historic_district",
        ["geom_2272"],
        unique=False,
        postgresql_using="gist",
        postgresql_ops={},
    )
    op.create_geospatial_index(
        "idx_historic_district_geom_4326",
        "historic_district",
        ["geom_4326"],
        unique=False,
        postgresql_using="gist",
        postgresql_ops={},
    )
    op.create_index(
        op.f("ix_historic_district_external_id"),
        "historic_district",
        ["external_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_historic_district_name"), "historic_district", ["name"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_historic_district_name"), table_name="historic_district")
    op.drop_index(op.f("ix_historic_district_external_id"), table_name="historic_district")
    op.drop_geospatial_index(
        "idx_historic_district_geom_4326",
        table_name="historic_district",
        postgresql_using="gist",
        column_name="geom_4326",
    )
    op.drop_geospatial_index(
        "idx_historic_district_geom_2272",
        table_name="historic_district",
        postgresql_using="gist",
        column_name="geom_2272",
    )
    op.drop_geospatial_table("historic_district")
