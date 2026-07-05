from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import Settings
from lotscope.ingestion.arcgis import ArcGisClient, ArcGisFeature
from lotscope.ingestion.loaders.overlays import to_overlay_row, to_rco_row
from lotscope.ingestion.models import DatasetFreshness

_GEOMETRY = {
    "type": "Polygon",
    "coordinates": [
        [[-75.16, 39.95], [-75.16, 39.951], [-75.159, 39.951], [-75.159, 39.95], [-75.16, 39.95]]
    ],
}
LAYER_URL = "http://arcgis.test/FeatureServer/0/query"


def test_to_overlay_row_maps_symbol_name_and_geometry() -> None:
    row = to_overlay_row(
        ArcGisFeature(
            geometry=_GEOMETRY,
            properties={
                "objectid": 12,
                "overlay_symbol": "/NCA",
                "overlay_name": "Neighborhood Commercial Area Overlay",
                "code_section": "14-503(4)",
            },
        )
    )
    assert row is not None
    assert row["external_id"] == "12"
    assert row["code"] == "/NCA"
    assert row["name"] == "Neighborhood Commercial Area Overlay"
    assert row["code_section"] == "14-503(4)"
    assert "geom_local" in row


def test_to_rco_row_maps_name_and_skips_without_geometry() -> None:
    row = to_rco_row(
        ArcGisFeature(
            geometry=_GEOMETRY,
            properties={
                "objectid": 3,
                "organization_name": "Girard Estate Neighbors",
                "org_type": "Other",
            },
        )
    )
    assert row is not None
    assert row["external_id"] == "3"
    assert row["name"] == "Girard Estate Neighbors"
    assert row["org_type"] == "Other"

    assert to_rco_row(ArcGisFeature(geometry=None, properties={"objectid": 3})) is None


class _FeatureHandler:
    def __init__(self, pages: list[list[dict[str, Any]]]) -> None:
        self._pages = pages
        self.calls = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        index = min(self.calls, len(self._pages) - 1)
        self.calls += 1
        return httpx.Response(
            200, json={"type": "FeatureCollection", "features": self._pages[index]}
        )


def _settings() -> Settings:
    return Settings(_env_file=None, http_backoff_seconds=0.0)


def _overlay_feature(object_id: int) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": _GEOMETRY,
        "properties": {"objectid": object_id, "overlay_symbol": "/NCA", "overlay_name": "NCA"},
    }


def _rco_feature(object_id: int) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": _GEOMETRY,
        "properties": {"objectid": object_id, "organization_name": "Test RCO"},
    }


@pytest.mark.integration
async def test_load_zoning_overlays_writes_geometry(db_session: AsyncSession) -> None:
    from lotscope.ingestion.loaders.overlays import load_zoning_overlays

    handler = _FeatureHandler([[_overlay_feature(1)]])
    async with ArcGisClient(_settings(), transport=httpx.MockTransport(handler)) as arcgis:
        total = await load_zoning_overlays(db_session, arcgis, layer_url=LAYER_URL, page_size=500)
    await db_session.flush()

    assert total == 1
    row = (
        await db_session.execute(
            text(
                "SELECT code, ST_SRID(geom_local), ST_SRID(geom_4326) FROM zoning_overlay "
                "WHERE external_id = '1'"
            )
        )
    ).one()
    assert row[0] == "/NCA"
    assert row[1] == 2272
    assert row[2] == 4326
    fresh = await db_session.get(DatasetFreshness, ("phl", "zoning_overlays"))
    assert fresh is not None
    assert fresh.status == "success"


@pytest.mark.integration
async def test_load_rco_writes_and_is_idempotent(db_session: AsyncSession) -> None:
    from lotscope.ingestion.loaders.overlays import load_rco

    pages = [[_rco_feature(5)]]
    for _ in range(2):
        handler = _FeatureHandler(pages)
        async with ArcGisClient(_settings(), transport=httpx.MockTransport(handler)) as arcgis:
            await load_rco(db_session, arcgis, layer_url=LAYER_URL, page_size=500)
        await db_session.flush()

    count = await db_session.scalar(text("SELECT count(*) FROM rco WHERE external_id = '5'"))
    assert count == 1
    name = await db_session.scalar(text("SELECT name FROM rco WHERE external_id = '5'"))
    assert name == "Test RCO"
