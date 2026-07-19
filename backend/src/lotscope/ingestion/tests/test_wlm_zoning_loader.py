import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import Settings
from lotscope.ingestion.arcgis import ArcGisClient, ArcGisFeature
from lotscope.ingestion.loaders.wlm import (
    load_wlm_zoning,
    normalize_wilmington_zone,
    to_wlm_zoning_row,
)

_LAYER_URL = "https://services.arcgis.com/hQ3wdpbjO3fPf612/arcgis/rest/services/LUP/FeatureServer/0"


def test_normalize_strips_hundred_prefix_and_canonicalizes_dashes() -> None:
    cases = {
        "26R-3": "R-3",
        "26R-2": "R-2",
        "26R5-B": "R-5B",
        "26R5-C": "R-5C",
        "26R5A1": "R-5A1",
        "26R-5A": "R-5A",
        "26W4": "W-4",
        "26W1": "W-1",
        "26M-1": "M-1",
        "26M1": "M-1",
        "26C-1A": "C-1A",
        "26C-2A": "C-2A",
        "26R-2A": "R-2A",
        "26O": "O",
        "26R3": "R-3",
    }
    for raw, expected in cases.items():
        assert normalize_wilmington_zone(raw) == expected


def test_normalize_rejects_dirty_and_empty_values() -> None:
    for raw in ["HI", "CN", "OR", "", "26", None, " "]:
        assert normalize_wilmington_zone(raw) is None


def test_to_wlm_zoning_row_maps_key_and_base_code() -> None:
    row = to_wlm_zoning_row(ArcGisFeature(properties={"PRCLID": "2601320063", "ZONECODE": "26R-3"}))
    assert row == {
        "parcel_number": "wlm:2601320063",
        "market_code": "wlm",
        "base_zoning_code": "R-3",
    }


class _ZoningHandler:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
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
                        "geometry": None,
                        "properties": {"PRCLID": "2601320063", "ZONECODE": "26R5-B"},
                    }
                ],
            },
        )


def _settings() -> Settings:
    return Settings(_env_file=None, http_backoff_seconds=0.0)


@pytest.mark.integration
async def test_load_wlm_zoning_sets_base_zoning_code(db_session: AsyncSession) -> None:
    async with ArcGisClient(_settings(), transport=httpx.MockTransport(_ZoningHandler())) as arcgis:
        total = await load_wlm_zoning(db_session, arcgis, parcels_layer_url=_LAYER_URL)
    await db_session.flush()

    assert total == 1
    code = await db_session.scalar(
        text("SELECT base_zoning_code FROM parcel WHERE parcel_number = 'wlm:2601320063'")
    )
    assert code == "R-5B"
