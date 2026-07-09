from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b1d7e4a90c35"
down_revision: str | None = "c4f7a1e08d2b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BACKFILL_SQL = """
UPDATE parcel p SET resolved_zoning_code = sub.code, resolved_zoning_source = 'spatial'
FROM (
    SELECT DISTINCT ON (p2.parcel_number) p2.parcel_number, zd.code
    FROM parcel p2
    JOIN zoning_district zd ON zd.market_code = p2.market_code
        AND ST_Contains(zd.geom_local, ST_Centroid(p2.geom_local))
    WHERE (p2.base_zoning_code IS NULL OR p2.base_zoning_code = '')
        AND p2.geom_local IS NOT NULL
    ORDER BY p2.parcel_number,
        ST_Area(ST_Intersection(ST_MakeValid(zd.geom_local), ST_MakeValid(p2.geom_local))) DESC,
        zd.code ASC
) sub
WHERE p.parcel_number = sub.parcel_number
"""

_MVT_BODY = """
CREATE OR REPLACE FUNCTION parcels_mvt(z integer, x integer, y integer)
RETURNS bytea
LANGUAGE plpgsql
STABLE PARALLEL SAFE
AS $fn$
DECLARE tile bytea;
BEGIN
    WITH bounds AS (
        SELECT ST_TileEnvelope(z, x, y) AS env_3857,
               ST_Transform(ST_TileEnvelope(z, x, y), 4326) AS env_4326
    ),
    features AS (
        SELECT ST_AsMVTGeom(
                   ST_Transform(p.geom_4326, 3857), bounds.env_3857, 4096, 64, true
               ) AS geom,
               p.parcel_number, p.market_code, p.address, p.is_vacant, p.is_city_owned,
               coalesce(nullif(p.base_zoning_code, ''), p.resolved_zoning_code) AS base_zoning_code,
               round(pv.opportunity_score)::int AS opportunity_score,
               round(pv.buildability_score)::int AS buildability_score,
               round(pv.risk_score)::int AS risk_score,
               pv.can_build_by_right, pv.by_right_units,
               round(pv.max_height_ft)::int AS max_height_ft,
               round(pv.value_estimate_low)::int AS value_low,
               round(pv.value_estimate_high)::int AS value_high
        FROM parcel p CROSS JOIN bounds
        LEFT JOIN parcel_verdict pv ON pv.parcel_number = p.parcel_number
        WHERE p.geom_4326 IS NOT NULL AND p.geom_4326 && bounds.env_4326
          {zoom_filter}
    )
    SELECT ST_AsMVT(features, 'parcels', 4096, 'geom') INTO tile
    FROM features WHERE features.geom IS NOT NULL;
    RETURN COALESCE(tile, ''::bytea);
END;
$fn$;
"""


def upgrade() -> None:
    op.add_column("parcel", sa.Column("resolved_zoning_code", sa.String(length=20), nullable=True))
    op.add_column(
        "parcel", sa.Column("resolved_zoning_source", sa.String(length=20), nullable=True)
    )
    op.execute(_BACKFILL_SQL)
    op.execute(_MVT_BODY.format(zoom_filter="AND (z >= 15 OR p.is_vacant)"))


def downgrade() -> None:
    op.execute(
        _MVT_BODY.replace(
            "coalesce(nullif(p.base_zoning_code, ''), p.resolved_zoning_code) AS base_zoning_code",
            "p.base_zoning_code",
        ).format(zoom_filter="AND (z >= 15 OR p.is_vacant)")
    )
    op.drop_column("parcel", "resolved_zoning_source")
    op.drop_column("parcel", "resolved_zoning_code")
