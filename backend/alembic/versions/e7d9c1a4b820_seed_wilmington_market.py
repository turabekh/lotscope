import json
from collections.abc import Sequence

from alembic import op

revision: str = "e7d9c1a4b820"
down_revision: str | None = "f3a91c27b0d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SOURCE_CONFIG = json.dumps(
    {
        "firstmap_parcels_url": (
            "https://enterprise.firstmap.delaware.gov/arcgis/rest/services/"
            "PlanningCadastre/DE_StateParcels/FeatureServer/0"
        ),
        "wilmington_arcgis_url": (
            "https://services.arcgis.com/hQ3wdpbjO3fPf612/arcgis/rest/services"
        ),
        "sheriff_civilview_county_id": "24",
        "hundred_filter": "26",
    }
)

_COVERAGE = (
    "Wilmington city pilot — New Castle County (DE) assessment + FirstMap geometry; "
    "FMV-2024 reassessment (ratio ~1.0); reduced distress stack (sheriff, tax, flood, "
    "land bank; no open code-violation or vacancy feed); comps sourcing provisional; "
    "zoning from City GIS."
)


def upgrade() -> None:
    op.execute(
        "INSERT INTO market "
        "(code, name, state, url_slug, local_srid, map_center, map_bounds, default_zoom, "
        "timezone, recorder_url_template, deal_assumption_overrides, source_config, "
        "coverage_note, launch_status, assessment_ratio, created_at, updated_at) VALUES "
        "('wlm', 'Wilmington', 'DE', 'wilmington', 2235, "
        "'[-75.5466, 39.7459]'::jsonb, "
        "'[[-75.59, 39.71], [-75.495, 39.785]]'::jsonb, 13.0, 'America/New_York', "
        "'https://www3.newcastlede.gov/parcel/search/', "
        "'{}'::jsonb, "
        f"'{_SOURCE_CONFIG}'::jsonb, "
        f"'{_COVERAGE}', "
        "'pilot', 1.0, now(), now()) ON CONFLICT (code) DO NOTHING"
    )


def downgrade() -> None:
    op.execute("DELETE FROM market WHERE code = 'wlm'")
