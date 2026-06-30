from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import Settings
from lotscope.ingestion.arcgis import ArcGisClient, ArcGisFeature
from lotscope.ingestion.loaders.streets import load_streets, to_street_row
from lotscope.ingestion.models import DatasetFreshness

_GEOMETRY = {
    "type": "LineString",
    "coordinates": [[-75.16, 39.95], [-75.159, 39.951]],
}
LAYER_URL = "http://arcgis.test/FeatureServer/0/query"


def test_to_street_row_maps_name_class_and_geometry() -> None:
    feature = ArcGisFeature(
        geometry=_GEOMETRY,
        properties={"seg_id": 4421, "stname": "MARKET ST", "class": "2"},
    )
    row = to_street_row(feature)
    assert row is not None
    assert row["external_id"] == "4421"
    assert row["street_name"] == "MARKET ST"
    assert row["street_class"] == "2"
    assert "geom_2272" in row


def test_to_street_row_skips_without_geometry_or_id() -> None:
    assert to_street_row(ArcGisFeature(geometry=None, properties={"seg_id": 1})) is None
    assert to_street_row(ArcGisFeature(geometry=_GEOMETRY, properties={})) is None


def test_to_street_row_allows_missing_name() -> None:
    row = to_street_row(ArcGisFeature(geometry=_GEOMETRY, properties={"seg_id": 9}))
    assert row is not None
    assert row["street_name"] is None


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


def _feature(seg_id: int, name: str) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": _GEOMETRY,
        "properties": {"seg_id": seg_id, "stname": name, "class": "2"},
    }


@pytest.mark.integration
async def test_load_streets_writes_geometry(db_session: AsyncSession) -> None:
    handler = _FeatureHandler([[_feature(101, "MARKET ST")]])
    async with ArcGisClient(_settings(), transport=httpx.MockTransport(handler)) as arcgis:
        total = await load_streets(db_session, arcgis, layer_url=LAYER_URL, page_size=500)
    await db_session.flush()

    assert total == 1
    row = (
        await db_session.execute(
            text(
                "SELECT street_name, ST_SRID(geom_2272), ST_SRID(geom_4326) "
                "FROM street_centerline WHERE external_id = '101'"
            )
        )
    ).one()
    assert row[0] == "MARKET ST"
    assert row[1] == 2272
    assert row[2] == 4326

    fresh = await db_session.get(DatasetFreshness, "streets")
    assert fresh is not None
    assert fresh.status == "success"


@pytest.mark.integration
async def test_load_streets_is_idempotent(db_session: AsyncSession) -> None:
    pages = [[_feature(101, "MARKET ST")]]
    for _ in range(2):
        handler = _FeatureHandler(pages)
        async with ArcGisClient(_settings(), transport=httpx.MockTransport(handler)) as arcgis:
            await load_streets(db_session, arcgis, layer_url=LAYER_URL, page_size=500)
        await db_session.flush()

    count = await db_session.scalar(
        text("SELECT count(*) FROM street_centerline WHERE external_id = '101'")
    )
    assert count == 1
