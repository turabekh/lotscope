from collections.abc import Sequence

from alembic import op

revision: str = "90713605d09d"
down_revision: str | None = "b6b74e29cd61"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_GEOM_TABLES = (
    "parcel",
    "historic_district",
    "neighborhood",
    "street_centerline",
    "zoning_district",
    "zoning_overlay",
    "rco",
    "flood_zone",
)


def upgrade() -> None:
    for table in _GEOM_TABLES:
        op.execute(f"ALTER TABLE {table} RENAME COLUMN geom_2272 TO geom_local")
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN geom_local TYPE geometry(Geometry) USING geom_local"
        )
        op.execute(f"ALTER INDEX idx_{table}_geom_2272 RENAME TO idx_{table}_geom_local")


def downgrade() -> None:
    for table in _GEOM_TABLES:
        op.execute(f"ALTER INDEX idx_{table}_geom_local RENAME TO idx_{table}_geom_2272")
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN geom_local TYPE geometry(Geometry, 2272) "
            "USING ST_SetSRID(geom_local, 2272)"
        )
        op.execute(f"ALTER TABLE {table} RENAME COLUMN geom_local TO geom_2272")
