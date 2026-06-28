from collections.abc import Sequence

from alembic import op

revision: str = "b8d4f0a2c6e3"
down_revision: str | None = "a7c3e9f1d4b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_WITH_HEIGHT = """
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
               p.is_city_owned,
               p.base_zoning_code,
               round(pv.opportunity_score)::int AS opportunity_score,
               round(pv.buildability_score)::int AS buildability_score,
               round(pv.risk_score)::int AS risk_score,
               pv.can_build_by_right,
               pv.by_right_units,
               round(pv.max_height_ft)::int AS max_height_ft,
               round(pv.value_estimate_low)::int AS value_low,
               round(pv.value_estimate_high)::int AS value_high
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

_WITHOUT_HEIGHT = """
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
               p.is_city_owned,
               p.base_zoning_code,
               round(pv.opportunity_score)::int AS opportunity_score,
               round(pv.buildability_score)::int AS buildability_score,
               round(pv.risk_score)::int AS risk_score,
               pv.can_build_by_right,
               pv.by_right_units,
               round(pv.value_estimate_low)::int AS value_low,
               round(pv.value_estimate_high)::int AS value_high
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


def upgrade() -> None:
    op.execute(_WITH_HEIGHT)


def downgrade() -> None:
    op.execute(_WITHOUT_HEIGHT)
