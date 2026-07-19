from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import Settings
from lotscope.ingestion.arcgis import ArcGisClient, ArcGisFeature
from lotscope.ingestion.loaders.wlm_layers import (
    load_wlm_flood,
    load_wlm_public,
    to_wlm_flood_row,
    to_wlm_historic_row,
)

_BASE = "https://services.arcgis.com/hQ3wdpbjO3fPf612/arcgis/rest/services"

_GEOM = {
    "type": "Polygon",
    "coordinates": [
        [[614000, 642000], [614000, 642050], [614040, 642050], [614040, 642000], [614000, 642000]]
    ],
}


def test_to_wlm_flood_row_maps_zone_and_market() -> None:
    row = to_wlm_flood_row(
        ArcGisFeature(properties={"PRCLID": "2603710013", "FloodHaz": "AE"}, geometry=_GEOM)
    )
    assert row is not None
    assert row["external_id"] == "wlm-flood-2603710013"
    assert row["zone"] == "AE"
    assert row["market_code"] == "wlm"


def test_to_wlm_historic_row_requires_a_district_name() -> None:
    assert (
        to_wlm_historic_row(
            ArcGisFeature(properties={"PRCLID": "1", "HistoricC": " "}, geometry=_GEOM)
        )
        is None
    )
    row = to_wlm_historic_row(
        ArcGisFeature(
            properties={"PRCLID": "2603630293", "HistoricC": "East Side CHD"}, geometry=_GEOM
        )
    )
    assert row is not None
    assert row["name"] == "East Side CHD"
    assert row["market_code"] == "wlm"


class _LayerHandler:
    def __init__(self, by_layer: dict[str, list[dict[str, Any]]]) -> None:
        self._by_layer = by_layer
        self._seen: set[str] = set()

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        layer = next((k for k in self._by_layer if f"/{k}/" in path), None)
        key = f"{layer}:{request.url.params.get('resultOffset', '0')}"
        if layer is None or key in self._seen:
            return httpx.Response(200, json={"type": "FeatureCollection", "features": []})
        self._seen.add(key)
        return httpx.Response(
            200, json={"type": "FeatureCollection", "features": self._by_layer[layer]}
        )


def _settings() -> Settings:
    return Settings(_env_file=None, http_backoff_seconds=0.0)


@pytest.mark.integration
async def test_load_wlm_flood_writes_flood_zone_in_2235(db_session: AsyncSession) -> None:
    handler = _LayerHandler(
        {
            "10": [
                {
                    "type": "Feature",
                    "geometry": _GEOM,
                    "properties": {"PRCLID": "2603710013", "FloodHaz": "AE"},
                }
            ]
        }
    )
    async with ArcGisClient(_settings(), transport=httpx.MockTransport(handler)) as arcgis:
        total = await load_wlm_flood(db_session, arcgis, arcgis_base_url=_BASE)
    await db_session.flush()

    assert total == 1
    row = (
        await db_session.execute(
            text(
                "SELECT zone, market_code, ST_SRID(geom_local) FROM flood_zone WHERE external_id = 'wlm-flood-2603710013'"
            )
        )
    ).one()
    assert row[0] == "AE"
    assert row[1] == "wlm"
    assert row[2] == 2235


@pytest.mark.integration
async def test_load_wlm_public_flags_land_bank_parcels_city_owned(db_session: AsyncSession) -> None:
    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, market_code) VALUES ('wlm:2601320063', 'wlm')")
    )
    await db_session.flush()

    handler = _LayerHandler(
        {
            "0": [
                {
                    "type": "Feature",
                    "geometry": None,
                    "properties": {"L0NCC_REST_Parcel_Data_PRCLID": "2601320063"},
                }
            ]
        }
    )
    async with ArcGisClient(_settings(), transport=httpx.MockTransport(handler)) as arcgis:
        count = await load_wlm_public(db_session, arcgis, arcgis_base_url=_BASE)
    await db_session.flush()

    assert count == 1
    is_city_owned = await db_session.scalar(
        text("SELECT is_city_owned FROM parcel WHERE parcel_number = 'wlm:2601320063'")
    )
    assert is_city_owned is True
