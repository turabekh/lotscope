from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision: str = "d7a2f4b19c63"
down_revision: str | None = "c4e9a17b2d58"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _geom(srid: int) -> Geometry:
    return Geometry(
        srid=srid,
        dimension=2,
        spatial_index=False,
        from_text="ST_GeomFromEWKT",
        name="geometry",
    )


def _create_overlay_layer(table: str, extra: list[sa.Column[object]]) -> None:
    op.create_geospatial_table(
        table,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_id", sa.String(length=60), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        *extra,
        sa.Column("geom_2272", _geom(2272), nullable=True),
        sa.Column("geom_4326", _geom(4326), nullable=True),
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
        sa.Column("source", sa.String(length=120), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id", name=f"uq_{table}_external"),
    )
    op.create_geospatial_index(
        f"idx_{table}_geom_2272", table, ["geom_2272"], postgresql_using="gist"
    )
    op.create_geospatial_index(
        f"idx_{table}_geom_4326", table, ["geom_4326"], postgresql_using="gist"
    )
    op.create_index(op.f(f"ix_{table}_external_id"), table, ["external_id"], unique=False)
    op.create_index(op.f(f"ix_{table}_name"), table, ["name"], unique=False)


def _drop_overlay_layer(table: str) -> None:
    op.drop_index(op.f(f"ix_{table}_name"), table_name=table)
    op.drop_index(op.f(f"ix_{table}_external_id"), table_name=table)
    op.drop_geospatial_index(
        f"idx_{table}_geom_4326",
        table_name=table,
        postgresql_using="gist",
        column_name="geom_4326",
    )
    op.drop_geospatial_index(
        f"idx_{table}_geom_2272",
        table_name=table,
        postgresql_using="gist",
        column_name="geom_2272",
    )
    op.drop_geospatial_table(table)


def upgrade() -> None:
    _create_overlay_layer(
        "zoning_overlay",
        [
            sa.Column("code", sa.String(length=30), nullable=True),
            sa.Column("code_section", sa.String(length=60), nullable=True),
        ],
    )
    op.create_index(op.f("ix_zoning_overlay_code"), "zoning_overlay", ["code"], unique=False)
    _create_overlay_layer(
        "rco",
        [sa.Column("org_type", sa.String(length=60), nullable=True)],
    )


def downgrade() -> None:
    _drop_overlay_layer("rco")
    op.drop_index(op.f("ix_zoning_overlay_code"), table_name="zoning_overlay")
    _drop_overlay_layer("zoning_overlay")
