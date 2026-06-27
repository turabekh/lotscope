from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
import geoalchemy2


revision: str = '28160d9c6701'
down_revision: str | None = 'f68b8f9c0860'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_PARCELS_MVT = """
CREATE OR REPLACE FUNCTION parcels_mvt(z integer, x integer, y integer)
RETURNS bytea
LANGUAGE plpgsql
STABLE
PARALLEL SAFE
AS $func$
DECLARE
    tile bytea;
BEGIN
    WITH bounds AS (
        SELECT ST_TileEnvelope(z, x, y) AS env_3857,
               ST_Transform(ST_TileEnvelope(z, x, y), 4326) AS env_4326
    ),
    features AS (
        SELECT ST_AsMVTGeom(ST_Transform(p.geom_4326, 3857), bounds.env_3857, 4096, 64, true) AS geom,
               p.parcel_number,
               p.address,
               p.is_vacant,
               p.base_zoning_code
        FROM parcel p, bounds
        WHERE p.geom_4326 IS NOT NULL
          AND p.geom_4326 && bounds.env_4326
    )
    SELECT ST_AsMVT(features, 'parcels', 4096, 'geom')
    INTO tile
    FROM features
    WHERE features.geom IS NOT NULL;
    RETURN COALESCE(tile, ''::bytea);
END;
$func$;
"""

_VACANT_LOTS_MVT = """
CREATE OR REPLACE FUNCTION vacant_lots_mvt(z integer, x integer, y integer)
RETURNS bytea
LANGUAGE plpgsql
STABLE
PARALLEL SAFE
AS $func$
DECLARE
    tile bytea;
BEGIN
    WITH bounds AS (
        SELECT ST_TileEnvelope(z, x, y) AS env_3857,
               ST_Transform(ST_TileEnvelope(z, x, y), 4326) AS env_4326
    ),
    features AS (
        SELECT ST_AsMVTGeom(ST_Transform(p.geom_4326, 3857), bounds.env_3857, 4096, 64, true) AS geom,
               p.parcel_number,
               p.address,
               p.vacancy_confidence,
               p.base_zoning_code
        FROM parcel p, bounds
        WHERE p.geom_4326 IS NOT NULL
          AND p.is_vacant IS TRUE
          AND p.geom_4326 && bounds.env_4326
    )
    SELECT ST_AsMVT(features, 'vacant_lots', 4096, 'geom')
    INTO tile
    FROM features
    WHERE features.geom IS NOT NULL;
    RETURN COALESCE(tile, ''::bytea);
END;
$func$;
"""


def upgrade() -> None:
    op.execute(_PARCELS_MVT)
    op.execute(_VACANT_LOTS_MVT)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS vacant_lots_mvt(integer, integer, integer)")
    op.execute("DROP FUNCTION IF EXISTS parcels_mvt(integer, integer, integer)")
