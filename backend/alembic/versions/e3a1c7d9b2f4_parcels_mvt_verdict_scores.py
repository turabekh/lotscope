from collections.abc import Sequence

from alembic import op

revision: str = "e3a1c7d9b2f4"
down_revision: str | None = "d2e4f6a8b0c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_WITH_SCORES = """
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
               p.base_zoning_code,
               round(pv.opportunity_score)::int AS opportunity_score,
               round(pv.risk_score)::int AS risk_score
        FROM parcel p
        CROSS JOIN bounds
        LEFT JOIN parcel_verdict pv ON pv.parcel_number = p.parcel_number
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

_WITHOUT_SCORES = """
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


def upgrade() -> None:
    op.execute(_WITH_SCORES)


def downgrade() -> None:
    op.execute(_WITHOUT_SCORES)
