from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import Settings
from lotscope.ingestion.arcgis import ArcGisClient, ArcGisFeature
from lotscope.ingestion.loaders.wlm import load_wlm_parcels, to_wlm_parcel_row
from lotscope.ingestion.models import DatasetFreshness

_GEOM_2235: dict[str, Any] = {
    "type": "Polygon",
    "coordinates": [
        [
            [614000.0, 642000.0],
            [614000.0, 642100.0],
            [614100.0, 642100.0],
            [614100.0, 642000.0],
            [614000.0, 642000.0],
        ]
    ],
}

_PARCELS_URL = "https://firstmap.test/DE_StateParcels/FeatureServer/0"


def test_to_wlm_parcel_row_maps_key_and_geometry() -> None:
    row = to_wlm_parcel_row(ArcGisFeature(properties={"PIN": "2600630067"}, geometry=_GEOM_2235))
    assert row is not None
    assert row["parcel_number"] == "wlm:2600630067"
    assert row["market_code"] == "wlm"
    assert row["lot_area_source"] == "geometry"
    assert "geom_local" in row
    assert "geom_4326" in row


def test_to_wlm_parcel_row_skips_without_key_or_geometry() -> None:
    assert to_wlm_parcel_row(ArcGisFeature(properties={"PIN": None}, geometry=_GEOM_2235)) is None
    assert to_wlm_parcel_row(ArcGisFeature(properties={"PIN": "2600630067"}, geometry=None)) is None


class _FeaturesHandler:
    def __init__(self) -> None:
        self.calls = 0
        self.where: str | None = None
        self.out_sr: str | None = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.where = request.url.params.get("where")
        self.out_sr = request.url.params.get("outSR")
        self.calls += 1
        if self.calls > 1:
            return httpx.Response(200, json={"type": "FeatureCollection", "features": []})
        return httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": _GEOM_2235,
                        "properties": {"PIN": "2600630067"},
                    }
                ],
            },
        )


def _settings() -> Settings:
    return Settings(_env_file=None, http_backoff_seconds=0.0)


@pytest.mark.integration
async def test_load_wlm_writes_dual_srid_2235_geometry(db_session: AsyncSession) -> None:
    handler = _FeaturesHandler()
    async with ArcGisClient(_settings(), transport=httpx.MockTransport(handler)) as arcgis:
        total = await load_wlm_parcels(
            db_session, arcgis, parcels_url=_PARCELS_URL, hundred="26", page_size=2000
        )
    await db_session.flush()

    assert total == 1
    assert handler.where == "PIN LIKE '26%'"
    assert handler.out_sr == "2235"

    row = (
        await db_session.execute(
            text(
                "SELECT ST_SRID(geom_local), ST_SRID(geom_4326), market_code, "
                "lot_area_sqft, lot_area_source FROM parcel WHERE parcel_number = :pn"
            ),
            {"pn": "wlm:2600630067"},
        )
    ).one()
    assert row[0] == 2235
    assert row[1] == 4326
    assert row[2] == "wlm"
    assert float(row[3]) == pytest.approx(10000.0, rel=0.001)
    assert row[4] == "geometry"

    fresh = await db_session.get(DatasetFreshness, ("wlm", "firstmap_parcels"))
    assert fresh is not None
    assert fresh.status == "success"


@pytest.mark.integration
async def test_load_wlm_geometry_does_not_clobber_existing_assessment(
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code, owner, market_value) "
            "VALUES ('wlm:2600630067', 'wlm', 'NCC Owner', 250000)"
        )
    )
    await db_session.flush()

    async with ArcGisClient(
        _settings(), transport=httpx.MockTransport(_FeaturesHandler())
    ) as arcgis:
        await load_wlm_parcels(db_session, arcgis, parcels_url=_PARCELS_URL, hundred="26")
    await db_session.flush()

    row = (
        await db_session.execute(
            text(
                "SELECT owner, market_value, ST_SRID(geom_local) "
                "FROM parcel WHERE parcel_number = :pn"
            ),
            {"pn": "wlm:2600630067"},
        )
    ).one()
    assert row[0] == "NCC Owner"
    assert float(row[1]) == 250000.0
    assert row[2] == 2235
