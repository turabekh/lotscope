from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e0d6365b0270"
down_revision: str | None = "9a52d71298f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PARCELS_MVT = """
CREATE OR REPLACE FUNCTION parcels_mvt(z integer, x integer, y integer)
RETURNS bytea LANGUAGE plpgsql STABLE PARALLEL SAFE AS $function$
DECLARE tile bytea;
BEGIN
    WITH bounds AS (
        SELECT ST_TileEnvelope(z, x, y) AS env_3857,
               ST_Transform(ST_TileEnvelope(z, x, y), 4326) AS env_4326
    ),
    features AS (
        SELECT ST_AsMVTGeom(ST_Transform(p.geom_4326, 3857), bounds.env_3857, 4096, 64, true) AS geom,
               p.parcel_number, p.market_code, p.address, p.is_vacant, p.is_city_owned,
               p.base_zoning_code,
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
    )
    SELECT ST_AsMVT(features, 'parcels', 4096, 'geom') INTO tile
    FROM features WHERE features.geom IS NOT NULL;
    RETURN COALESCE(tile, ''::bytea);
END;
$function$
"""

_VACANT_MVT = """
CREATE OR REPLACE FUNCTION vacant_lots_mvt(z integer, x integer, y integer)
RETURNS bytea LANGUAGE plpgsql STABLE PARALLEL SAFE AS $function$
DECLARE tile bytea;
BEGIN
    WITH bounds AS (
        SELECT ST_TileEnvelope(z, x, y) AS env_3857,
               ST_Transform(ST_TileEnvelope(z, x, y), 4326) AS env_4326
    ),
    features AS (
        SELECT ST_AsMVTGeom(ST_Transform(p.geom_4326, 3857), bounds.env_3857, 4096, 64, true) AS geom,
               p.parcel_number, p.market_code, p.address, p.vacancy_confidence, p.base_zoning_code
        FROM parcel p, bounds
        WHERE p.geom_4326 IS NOT NULL AND p.is_vacant IS TRUE
          AND p.geom_4326 && bounds.env_4326
    )
    SELECT ST_AsMVT(features, 'vacant_lots', 4096, 'geom') INTO tile
    FROM features WHERE features.geom IS NOT NULL;
    RETURN COALESCE(tile, ''::bytea);
END;
$function$
"""


def upgrade() -> None:
    op.add_column(
        "saved_search", sa.Column("market_code", sa.String(length=10), nullable=True)
    )
    op.execute("UPDATE saved_search SET market_code = 'phl'")
    op.alter_column("saved_search", "market_code", server_default="phl", nullable=False)
    op.create_index("ix_saved_search_market_code", "saved_search", ["market_code"])
    op.create_foreign_key(
        "saved_search_market_code_fkey", "saved_search", "market", ["market_code"], ["code"]
    )
    op.execute(_PARCELS_MVT)
    op.execute(_VACANT_MVT)


def downgrade() -> None:
    op.execute(_PARCELS_MVT.replace("p.market_code, ", ""))
    op.execute(_VACANT_MVT.replace("p.market_code, ", ""))
    op.drop_constraint("saved_search_market_code_fkey", "saved_search", type_="foreignkey")
    op.drop_index("ix_saved_search_market_code", table_name="saved_search")
    op.drop_column("saved_search", "market_code")
