from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import Settings
from lotscope.ingestion.arcgis import ArcGisClient, ArcGisFeature
from lotscope.ingestion.loaders.neighborhoods import load_neighborhoods, to_neighborhood_row
from lotscope.ingestion.models import DatasetFreshness

_GEOMETRY = {
    "type": "Polygon",
    "coordinates": [
        [[-75.16, 39.95], [-75.16, 39.951], [-75.159, 39.951], [-75.159, 39.95], [-75.16, 39.95]]
    ],
}
LAYER_URL = "http://arcgis.test/FeatureServer/0/query"


def test_to_neighborhood_row_maps_name_and_geometry() -> None:
    feature = ArcGisFeature(geometry=_GEOMETRY, properties={"ObjectId": 7, "id": "Fishtown"})
    row = to_neighborhood_row(feature)
    assert row is not None
    assert row["external_id"] == "7"
    assert row["name"] == "Fishtown"
    assert "geom_local" in row


def test_to_neighborhood_row_skips_without_geometry_or_name() -> None:
    assert (
        to_neighborhood_row(ArcGisFeature(geometry=None, properties={"ObjectId": 1, "id": "X"}))
        is None
    )
    assert (
        to_neighborhood_row(ArcGisFeature(geometry=_GEOMETRY, properties={"ObjectId": 1})) is None
    )


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


def _feature(object_id: int, name: str) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": _GEOMETRY,
        "properties": {"ObjectId": object_id, "id": name},
    }


@pytest.mark.integration
async def test_load_neighborhoods_writes_geometry(db_session: AsyncSession) -> None:
    handler = _FeatureHandler([[_feature(1, "Fishtown")]])
    async with ArcGisClient(_settings(), transport=httpx.MockTransport(handler)) as arcgis:
        total = await load_neighborhoods(db_session, arcgis, layer_url=LAYER_URL, page_size=500)
    await db_session.flush()

    assert total == 1
    row = (
        await db_session.execute(
            text(
                "SELECT name, ST_SRID(geom_local), ST_SRID(geom_4326) FROM neighborhood "
                "WHERE external_id = '1'"
            )
        )
    ).one()
    assert row[0] == "Fishtown"
    assert row[1] == 2272
    assert row[2] == 4326

    fresh = await db_session.get(DatasetFreshness, "neighborhoods")
    assert fresh is not None
    assert fresh.status == "success"


@pytest.mark.integration
async def test_load_neighborhoods_is_idempotent(db_session: AsyncSession) -> None:
    pages = [[_feature(1, "Fishtown")]]
    for _ in range(2):
        handler = _FeatureHandler(pages)
        async with ArcGisClient(_settings(), transport=httpx.MockTransport(handler)) as arcgis:
            await load_neighborhoods(db_session, arcgis, layer_url=LAYER_URL, page_size=500)
        await db_session.flush()

    count = await db_session.scalar(
        text("SELECT count(*) FROM neighborhood WHERE external_id = '1'")
    )
    assert count == 1
