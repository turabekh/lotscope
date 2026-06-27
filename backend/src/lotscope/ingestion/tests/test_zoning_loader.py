from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import Settings
from lotscope.ingestion.arcgis import ArcGisClient, ArcGisFeature
from lotscope.ingestion.loaders.zoning import to_zoning_row
from lotscope.ingestion.models import DatasetFreshness

_GEOMETRY = {
    "type": "Polygon",
    "coordinates": [
        [[-75.16, 39.95], [-75.16, 39.951], [-75.159, 39.951], [-75.159, 39.95], [-75.16, 39.95]]
    ],
}
LAYER_URL = "http://arcgis.test/FeatureServer/0/query"


def test_to_zoning_row_maps_code_and_geometry() -> None:
    feature = ArcGisFeature(
        geometry=_GEOMETRY,
        properties={"OBJECTID": 7, "CODE": "RSA5", "LONG_CODE": "RSA-5"},
    )
    row = to_zoning_row(feature)
    assert row is not None
    assert row["external_id"] == "7"
    assert row["code"] == "RSA5"
    assert row["long_code"] == "RSA-5"
    assert "geom_2272" in row


def test_to_zoning_row_skips_without_geometry_or_code() -> None:
    assert (
        to_zoning_row(ArcGisFeature(geometry=None, properties={"OBJECTID": 1, "CODE": "RSA5"}))
        is None
    )
    assert to_zoning_row(ArcGisFeature(geometry=_GEOMETRY, properties={"OBJECTID": 1})) is None


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


def _feature(object_id: int, code: str) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": _GEOMETRY,
        "properties": {"OBJECTID": object_id, "CODE": code, "LONG_CODE": code},
    }


@pytest.mark.integration
async def test_load_zoning_districts_writes_geometry(db_session: AsyncSession) -> None:
    from lotscope.ingestion.loaders.zoning import load_zoning_districts

    handler = _FeatureHandler([[_feature(1, "RSA5")]])
    async with ArcGisClient(_settings(), transport=httpx.MockTransport(handler)) as arcgis:
        total = await load_zoning_districts(db_session, arcgis, layer_url=LAYER_URL, page_size=500)
    await db_session.flush()

    assert total == 1
    row = (
        await db_session.execute(
            text(
                "SELECT code, ST_SRID(geom_2272), ST_SRID(geom_4326) FROM zoning_district "
                "WHERE external_id = '1'"
            )
        )
    ).one()
    assert row[0] == "RSA5"
    assert row[1] == 2272
    assert row[2] == 4326

    fresh = await db_session.get(DatasetFreshness, "zoning_base_districts")
    assert fresh is not None
    assert fresh.status == "success"


@pytest.mark.integration
async def test_load_zoning_districts_is_idempotent(db_session: AsyncSession) -> None:
    from lotscope.ingestion.loaders.zoning import load_zoning_districts

    pages = [[_feature(1, "RSA5")]]
    for _ in range(2):
        handler = _FeatureHandler(pages)
        async with ArcGisClient(_settings(), transport=httpx.MockTransport(handler)) as arcgis:
            await load_zoning_districts(db_session, arcgis, layer_url=LAYER_URL, page_size=500)
        await db_session.flush()

    count = await db_session.scalar(
        text("SELECT count(*) FROM zoning_district WHERE external_id = '1'")
    )
    assert count == 1
