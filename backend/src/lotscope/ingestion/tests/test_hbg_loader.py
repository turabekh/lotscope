from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import Settings
from lotscope.ingestion.arcgis import ArcGisClient, ArcGisFeature
from lotscope.ingestion.loaders.hbg import _mailing, _owner, _parcel_row, _situs, load_hbg_parcels
from lotscope.ingestion.models import DatasetFreshness

# A small square in EPSG:2272 (feet), near downtown Harrisburg.
_GEOMETRY = {
    "type": "Polygon",
    "coordinates": [
        [
            [2209463.0, 339313.0],
            [2209463.0, 339363.0],
            [2209513.0, 339363.0],
            [2209513.0, 339313.0],
            [2209463.0, 339313.0],
        ]
    ],
}


def _props(**overrides: Any) -> dict[str, Any]:
    base = {
        "property_i": "04-038-028",
        "house_numb": "305",
        "street_nam": "FRONT ST",
        "street_suf": "0",
        "land": 900,
        "building": 9300,
        "py_used_co": "C15",
        "last_name": "305 FRONT STREET INVESTORS LLC",
        "first_name": "0",
        "org_indi_f": "O",
        "address1": "4732 GETTYSBURG RD",
        "city": "MECHANICSBURG",
        "state_code": "PA",
        "zip_code": "17055",
    }
    base.update(overrides)
    return base


def test_owner_org_uses_last_name_individual_is_last_first() -> None:
    assert _owner(_props()) == "305 FRONT STREET INVESTORS LLC"
    assert _owner(_props(org_indi_f="I", last_name="PITTS", first_name="TASHA")) == "PITTS, TASHA"


def test_situs_and_mailing_drop_zero_sentinels() -> None:
    assert _situs(_props()) == "305 FRONT ST"
    assert _mailing(_props()) == "4732 GETTYSBURG RD, MECHANICSBURG, PA 17055"


def test_parcel_row_maps_key_values_and_use() -> None:
    feature = ArcGisFeature(geometry=_GEOMETRY, properties=_props())
    row = _parcel_row(feature, {"C15": "PARKING LOT"})
    assert row is not None
    assert row["parcel_number"] == "hbg:04-038-028"
    assert row["market_code"] == "hbg"
    assert row["coverage"] == "full"
    assert row["land_value"] == 900
    assert row["improvement_value"] == 9300
    assert row["market_value"] == 10200
    assert row["land_use"] == "PARKING LOT"


def test_parcel_row_skips_without_key_or_geometry() -> None:
    assert _parcel_row(ArcGisFeature(geometry=None, properties=_props()), {}) is None
    assert _parcel_row(ArcGisFeature(geometry=_GEOMETRY, properties={}), {}) is None


class _Router:
    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "DC_TAX_LANDUSE_CODES" in url:
            props = {"LANDUSE": "C15", "NAME": "PARKING LOT"}
            features = [{"type": "Feature", "properties": props}]
        else:
            features = [{"type": "Feature", "geometry": _GEOMETRY, "properties": _props()}]
        return httpx.Response(200, json={"type": "FeatureCollection", "features": features})


@pytest.mark.integration
async def test_load_hbg_parcels_writes_spine_geometry_and_freshness(
    db_session: AsyncSession,
) -> None:
    settings = Settings(_env_file=None, http_backoff_seconds=0.0)
    async with ArcGisClient(settings, transport=httpx.MockTransport(_Router())) as arcgis:
        total = await load_hbg_parcels(
            db_session,
            arcgis,
            services_url="http://arcgis.test/rest/services",
            municipality="CITY OF HARRISBURG",
            page_size=500,
        )
    assert total == 1

    row = (
        await db_session.execute(
            text(
                "SELECT parcel_number, market_code, coverage, owner, address, land_use, "
                "market_value, ST_SRID(geom_local) AS srid, "
                "ST_SRID(geom_4326) AS srid4326, round(lot_area_sqft) AS area "
                "FROM parcel WHERE parcel_number = 'hbg:04-038-028'"
            )
        )
    ).one()
    assert row.market_code == "hbg"
    assert row.coverage == "full"
    assert row.owner == "305 FRONT STREET INVESTORS LLC"
    assert row.land_use == "PARKING LOT"
    assert row.market_value == 10200
    assert row.srid == 2272
    assert row.srid4326 == 4326
    assert row.area == 2500

    fresh = await db_session.get(DatasetFreshness, ("hbg", "dc_parcels"))
    assert fresh is not None
    assert fresh.status == "success"
