from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ea5bd26236ef"
down_revision: str | None = "e0d6365b0270"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_HBG_SEED = (
    "INSERT INTO market "
    "(code, name, state, url_slug, local_srid, map_center, map_bounds, default_zoom, "
    "timezone, recorder_url_template, deal_assumption_overrides, source_config, "
    "coverage_note, launch_status, created_at, updated_at) VALUES "
    "('hbg', 'Harrisburg', 'PA', 'harrisburg', 2272, "
    "'[-76.8844, 40.2732]'::jsonb, '[[-76.92, 40.245], [-76.85, 40.295]]'::jsonb, 13.5, "
    "'America/New_York', "
    "'https://www.dauphinpropertyinfo.org/search/CommonSearch.aspx?mode=REALPROP', "
    "'{\"deal_construction_cost_per_sqft\": 145.0}'::jsonb, "
    "'{\"arcgis_services_url\": "
    "\"https://services2.arcgis.com/EEtiX55QzkHKYQKY/arcgis/rest/services\", "
    "\"municipality_filter\": \"CITY OF HARRISBURG\"}'::jsonb, "
    "'Harrisburg city pilot — county assessment + geometry; no open sale-price comps "
    "and no code-enforcement feed; zoning provisional pending review.', "
    "'pilot', now(), now()) ON CONFLICT (code) DO NOTHING"
)


def upgrade() -> None:
    op.add_column(
        "parcel",
        sa.Column("coverage", sa.String(length=20), server_default="full", nullable=False),
    )
    op.execute(_HBG_SEED)


def downgrade() -> None:
    op.execute("DELETE FROM market WHERE code = 'hbg'")
    op.drop_column("parcel", "coverage")
