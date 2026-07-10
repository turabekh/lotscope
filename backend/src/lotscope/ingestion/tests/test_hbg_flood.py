from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import Settings
from lotscope.ingestion.arcgis import ArcGisClient, ArcGisFeature
from lotscope.ingestion.loaders.hbg import flood_zone_value, hbg_flood_row, load_hbg_flood

_ZONE_GEOM = {
    "type": "Polygon",
    "coordinates": [
        [
            [-76.885, 40.265],
            [-76.885, 40.275],
            [-76.875, 40.275],
            [-76.875, 40.265],
            [-76.885, 40.265],
        ]
    ],
}


def test_flood_zone_value_drops_absent() -> None:
    assert flood_zone_value({"floodzone": "N/A"}) is None
    assert flood_zone_value({"floodzone": ""}) is None
    assert flood_zone_value({"floodzone": None}) is None
    assert flood_zone_value({"floodzone": "100 Year"}) == "100 Year"


def test_hbg_flood_row_namespaces_and_maps() -> None:
    row = hbg_flood_row(
        ArcGisFeature(id=7, geometry=_ZONE_GEOM, properties={"floodzone": "100 Year"})
    )
    assert row is not None
    assert row["external_id"] == "hbg:flood:7"
    assert row["zone"] == "100 Year"
    assert row["market_code"] == "hbg"
    assert "geom_local" in row


def test_hbg_flood_row_skips_non_flood() -> None:
    assert (
        hbg_flood_row(ArcGisFeature(id=8, geometry=_ZONE_GEOM, properties={"floodzone": "N/A"}))
        is None
    )
    assert (
        hbg_flood_row(ArcGisFeature(id=9, geometry=None, properties={"floodzone": "100 Year"}))
        is None
    )


class _FeatureHandler:
    def __init__(self, features: list[dict[str, Any]]) -> None:
        self._features = features
        self.calls = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        features = self._features if self.calls == 0 else []
        self.calls += 1
        return httpx.Response(200, json={"type": "FeatureCollection", "features": features})


def _settings() -> Settings:
    return Settings(_env_file=None, http_backoff_seconds=0.0)


def _feature(object_id: int, zone: str) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": _ZONE_GEOM,
        "properties": {"floodzone": zone},
        "id": object_id,
    }


_FLOOD_QUERY = text(
    "SELECT array_agg(DISTINCT fz.zone) FROM parcel p "
    "JOIN flood_zone fz ON fz.market_code = p.market_code "
    "AND ST_Intersects(fz.geom_local, p.geom_local) "
    "WHERE p.parcel_number = :pn AND fz.zone IS NOT NULL"
)


async def _insert_hbg_parcel(session: AsyncSession, parcel_number: str, wkt: str) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code, geom_4326, geom_local) VALUES "
            "(:pn, 'hbg', ST_SetSRID(ST_GeomFromText(:wkt), 4326), "
            "ST_Transform(ST_SetSRID(ST_GeomFromText(:wkt), 4326), 2272))"
        ),
        {"pn": parcel_number, "wkt": wkt},
    )


@pytest.mark.integration
async def test_load_hbg_flood_flags_intersecting_parcel(db_session: AsyncSession) -> None:
    handler = _FeatureHandler([_feature(1, "100 Year"), _feature(2, "N/A")])
    async with ArcGisClient(_settings(), transport=httpx.MockTransport(handler)) as arcgis:
        total = await load_hbg_flood(db_session, arcgis)
    await db_session.flush()

    assert total == 1
    zone_count = await db_session.scalar(
        text("SELECT count(*) FROM flood_zone WHERE market_code = 'hbg'")
    )
    assert zone_count == 1

    await _insert_hbg_parcel(
        db_session,
        "hbg:99-999-001",
        "POLYGON((-76.882 40.268, -76.882 40.272, -76.878 40.272, -76.878 40.268, -76.882 40.268))",
    )
    await _insert_hbg_parcel(
        db_session,
        "hbg:99-999-002",
        "POLYGON((-76.70 40.10, -76.70 40.11, -76.69 40.11, -76.69 40.10, -76.70 40.10))",
    )
    await db_session.flush()

    inside = await db_session.scalar(_FLOOD_QUERY, {"pn": "hbg:99-999-001"})
    outside = await db_session.scalar(_FLOOD_QUERY, {"pn": "hbg:99-999-002"})
    assert inside == ["100 Year"]
    assert outside is None
