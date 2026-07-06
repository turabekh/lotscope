import json
from collections.abc import Sequence

from alembic import op

revision: str = "d4f1a8c2e9b7"
down_revision: str | None = "c8e3a1f6b4d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SOURCE_CONFIG = json.dumps(
    {
        "ckan_base_url": "https://data.wprdc.org",
        "municipality_filter": "PITTSBURGH",
        "assessment_resource_id": "65855e14-549e-4992-b5be-d629afc676fa",
        "boundaries_resource_id": "3f50d47a-ab54-4da2-9f03-8519006e9fc9",
        "sales_resource_id": "5bbe6c55-bce6-4edb-9d04-68edeb6bf7b1",
        "liens_resource_id": "d1e80180-5b2e-4dab-8ec3-be621628649e",
        "violations_resource_id": "70c06278-92c5-4040-ab28-17671866f81c",
        "condemned_resource_id": "0a963f26-eb4b-4325-bbbc-3ddf6a871410",
        "city_owned_resource_id": "e1dcee82-9179-4306-8167-5891915b62a7",
        "foreclosures_resource_id": "859bccfd-0e12-4161-a348-313d734f25fd",
        "zoning_resource_id": "6127f35e-f36b-4a53-80b3-f4409609e9df",
        "neighborhoods_resource_id": "4af8e160-57e9-4ebf-a501-76ca1b42fc99",
    }
)

_COVERAGE = (
    "Pittsburgh city pilot — Allegheny County assessment + geometry via WPRDC; "
    "validation-filtered sale comps; PLI violations live; owner surfaces disabled "
    "(Ordinance 3478-07); zoning provisional pending review."
)


def upgrade() -> None:
    op.execute(
        "INSERT INTO market "
        "(code, name, state, url_slug, local_srid, map_center, map_bounds, default_zoom, "
        "timezone, recorder_url_template, deal_assumption_overrides, source_config, "
        "coverage_note, launch_status, assessment_ratio, created_at, updated_at) VALUES "
        "('pgh', 'Pittsburgh', 'PA', 'pittsburgh', 2272, "
        "'[-79.9959, 40.4406]'::jsonb, "
        "'[[-80.0954, 40.361], [-79.8656, 40.5012]]'::jsonb, 12.5, 'America/New_York', "
        "'https://gis.alleghenycounty.us/RealEstate/SearchResults.aspx?ParcelID={local_key}', "
        "'{}'::jsonb, "
        f"'{_SOURCE_CONFIG}'::jsonb, "
        f"'{_COVERAGE}', "
        "'pilot', 0.5014, now(), now()) ON CONFLICT (code) DO NOTHING"
    )


def downgrade() -> None:
    op.execute("DELETE FROM market WHERE code = 'pgh'")
