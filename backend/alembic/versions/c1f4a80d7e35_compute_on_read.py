"""the verdict is computed on read: a screening index replaces the stored verdict

Revision ID: c1f4a80d7e35
Revises: b9e2f77c31d4
Create Date: 2026-09-06

Hand-written: autogenerate emits destructive junk against this schema.

parcel_screen is seeded from parcel_verdict before that table is dropped, so search
ranking and the buy box do not go blank between this migration and the first nightly
rebuild. Everything else here is the ceremony that a stored verdict needed: the version
columns, the pre-sweep baselines, and the coverage stat that counted how much of the
table was current.
"""

import sqlalchemy as sa
from alembic import op

revision = "c1f4a80d7e35"
down_revision = "b9e2f77c31d4"
branch_labels = None
depends_on = None

_BASELINE_TABLES = (
    "pre_absentee_distress",
    "pre_d3_verdict",
    "pre_derived_vacancy",
    "pre_public_ownership",
    "pre_v11_distress",
    "pre_v11_verdict",
)

_MVT_ON_SCREEN = """
CREATE OR REPLACE FUNCTION parcels_mvt(z integer, x integer, y integer)
RETURNS bytea
LANGUAGE plpgsql STABLE PARALLEL SAFE
AS $$
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
               coalesce(nullif(p.base_zoning_code, ''), p.resolved_zoning_code)
                 AS base_zoning_code,
               round(ps.opportunity_score)::int AS opportunity_score,
               round(ps.risk_score)::int AS risk_score,
               ps.can_build_by_right, ps.by_right_units
        FROM parcel p CROSS JOIN bounds
        LEFT JOIN parcel_screen ps ON ps.parcel_number = p.parcel_number
        WHERE p.geom_4326 IS NOT NULL AND p.geom_4326 && bounds.env_4326
          AND (z >= 15 OR p.is_vacant)
    )
    SELECT ST_AsMVT(features, 'parcels', 4096, 'geom') INTO tile
    FROM features WHERE features.geom IS NOT NULL;
    RETURN COALESCE(tile, ''::bytea);
END;
$$;
"""

_MVT_ON_VERDICT = """
CREATE OR REPLACE FUNCTION parcels_mvt(z integer, x integer, y integer)
RETURNS bytea
LANGUAGE plpgsql STABLE PARALLEL SAFE
AS $$
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
               coalesce(nullif(p.base_zoning_code, ''), p.resolved_zoning_code)
                 AS base_zoning_code,
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
          AND (z >= 15 OR p.is_vacant)
    )
    SELECT ST_AsMVT(features, 'parcels', 4096, 'geom') INTO tile
    FROM features WHERE features.geom IS NOT NULL;
    RETURN COALESCE(tile, ''::bytea);
END;
$$;
"""


def upgrade() -> None:
    op.create_table(
        "parcel_screen",
        sa.Column("parcel_number", sa.String(length=40), primary_key=True),
        sa.Column("opportunity_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("deal_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("max_allowable_offer", sa.Numeric(14, 2), nullable=True),
        sa.Column("est_margin", sa.Numeric(14, 4), nullable=True),
        sa.Column("risk_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("by_right_units", sa.Integer(), nullable=True),
        sa.Column("can_build_by_right", sa.Boolean(), nullable=True),
        sa.Column("is_underpriced", sa.Boolean(), nullable=True),
        sa.Column("sources", sa.dialects.postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["parcel_number"], ["parcel.parcel_number"], ondelete="CASCADE"),
    )
    op.create_index("ix_parcel_screen_opportunity_score", "parcel_screen", ["opportunity_score"])

    # Carry what the sweep last computed, so nothing that ranks goes blank tonight.
    op.execute(
        "INSERT INTO parcel_screen (parcel_number, opportunity_score, deal_score, "
        "max_allowable_offer, est_margin, risk_score, by_right_units, can_build_by_right, "
        "is_underpriced, sources, computed_at) "
        "SELECT v.parcel_number, v.opportunity_score, v.deal_score, v.max_allowable_offer, "
        "v.est_margin, v.risk_score, v.by_right_units, v.can_build_by_right, "
        "v.is_underpriced, '[]'::jsonb, v.computed_at "
        "FROM parcel_verdict v JOIN parcel p USING (parcel_number) "
        "WHERE p.is_vacant IS TRUE "
        "ON CONFLICT (parcel_number) DO NOTHING"
    )

    # The map colours by the screening index now. The value range and the height came
    # off the tile with the table: a hover bubble carrying a figure from last night,
    # with no source and no as-of, is exactly the assertion this step removes.
    op.execute(_MVT_ON_SCREEN)

    op.drop_table("parcel_verdict")
    for table in _BASELINE_TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table}")

    op.drop_column("parcel_correction", "verdict_version")
    op.drop_column("parcel_distress", "version")
    op.drop_column("parcel_distress", "profile_id")

    op.alter_column("market_stats", "verdict_pct", new_column_name="screened_pct")
    op.alter_column("market_stats", "vacant_with_comp_pct", new_column_name="vacant_priced_pct")


def downgrade() -> None:
    op.alter_column("market_stats", "vacant_priced_pct", new_column_name="vacant_with_comp_pct")
    op.alter_column("market_stats", "screened_pct", new_column_name="verdict_pct")
    op.add_column("parcel_distress", sa.Column("profile_id", sa.String(length=40), nullable=True))
    op.add_column(
        "parcel_distress",
        sa.Column("version", sa.String(length=20), nullable=False, server_default="v2"),
    )
    op.add_column(
        "parcel_correction", sa.Column("verdict_version", sa.String(length=10), nullable=True)
    )

    # The baselines were snapshots of a sweep that no longer runs; they are not recreated.
    op.create_table(
        "parcel_verdict",
        sa.Column("parcel_number", sa.String(length=40), primary_key=True),
        sa.Column("verdict_version", sa.String(length=40), nullable=False),
        sa.Column("buildability_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("opportunity_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("can_build_by_right", sa.Boolean(), nullable=True),
        sa.Column("by_right_units", sa.Integer(), nullable=True),
        sa.Column("max_height_ft", sa.Numeric(10, 2), nullable=True),
        sa.Column("needs_variance", sa.Boolean(), nullable=True),
        sa.Column("buildable_area_sqft", sa.Numeric(14, 2), nullable=True),
        sa.Column("value_estimate_low", sa.Numeric(14, 2), nullable=True),
        sa.Column("value_estimate_high", sa.Numeric(14, 2), nullable=True),
        sa.Column("value_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("assessment_market_gap", sa.Numeric(14, 2), nullable=True),
        sa.Column("arv", sa.Numeric(14, 2), nullable=True),
        sa.Column("est_profit", sa.Numeric(14, 2), nullable=True),
        sa.Column("est_margin", sa.Numeric(14, 4), nullable=True),
        sa.Column("max_allowable_offer", sa.Numeric(14, 2), nullable=True),
        sa.Column("deal_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("is_underpriced", sa.Boolean(), nullable=True),
        sa.Column("risk_score", sa.Numeric(5, 2), nullable=True),
        sa.Column(
            "risk_flags", sa.dialects.postgresql.JSONB(), nullable=False, server_default="[]"
        ),
        sa.Column("field_trust", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("recommendation", sa.String(length=40), nullable=True),
        sa.Column("recommendation_reason", sa.Text(), nullable=True),
        sa.Column("decision_version", sa.String(length=10), nullable=True),
        sa.Column("sources", sa.dialects.postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["parcel_number"], ["parcel.parcel_number"], ondelete="CASCADE"),
    )
    op.execute(_MVT_ON_VERDICT)
    op.drop_index("ix_parcel_screen_opportunity_score", table_name="parcel_screen")
    op.drop_table("parcel_screen")
