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


# A small polygon in EPSG:4326, near downtown Harrisburg (for the districts loader).
_GEOMETRY_4326 = {
    "type": "Polygon",
    "coordinates": [
        [
            [-76.885, 40.273],
            [-76.885, 40.274],
            [-76.884, 40.274],
            [-76.884, 40.273],
            [-76.885, 40.273],
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


def test_district_row_maps_code_and_market() -> None:
    from lotscope.ingestion.loaders.hbg import _district_row

    feature = ArcGisFeature(
        id=42, geometry=_GEOMETRY_4326, properties={"MAP_ACRONY": "CG"}
    )
    row = _district_row(feature)
    assert row is not None
    assert row["external_id"] == "hbg:42"
    assert row["code"] == "CG"
    assert row["market_code"] == "hbg"
    assert row["source"] == "tcrp_zoning"


@pytest.mark.integration
async def test_load_hbg_zoning_districts_writes_geometry(db_session: AsyncSession) -> None:
    from lotscope.ingestion.loaders.hbg import load_hbg_zoning_districts

    settings = Settings(_env_file=None, http_backoff_seconds=0.0)

    def _handler(_request: httpx.Request) -> httpx.Response:
        feature = {
            "type": "Feature",
            "id": 42,
            "geometry": _GEOMETRY_4326,
            "properties": {"MAP_ACRONY": "CG"},
        }
        return httpx.Response(200, json={"type": "FeatureCollection", "features": [feature]})

    async with ArcGisClient(settings, transport=httpx.MockTransport(_handler)) as arcgis:
        total = await load_hbg_zoning_districts(
            db_session, arcgis, services_url="http://arcgis.test/rest/services", page_size=500
        )
    assert total == 1
    row = (
        await db_session.execute(
            text(
                "SELECT code, market_code, ST_SRID(geom_local) srid FROM zoning_district "
                "WHERE external_id = 'hbg:42'"
            )
        )
    ).one()
    assert row.code == "CG"
    assert row.market_code == "hbg"
    assert row.srid == 2272


def test_public_owner_matches_authorities_not_private_llcs() -> None:
    from lotscope.ingestion.loaders.hbg import is_hbg_public_owner

    assert is_hbg_public_owner("REDEVELOPMENT AUTHORITY OF CITY OF HARRISBURG")
    assert is_hbg_public_owner("HARRISBURG HOUSING AUTHORITY")
    assert is_hbg_public_owner("COUNTY OF DAUPHIN")
    assert is_hbg_public_owner("CITY OF HARRISBURG")
    assert not is_hbg_public_owner("HARRISBURG REDEVELOPMENT GROUP LLC")
    assert not is_hbg_public_owner("MIDTOWN REDEVELOPMENT LLC")
    assert not is_hbg_public_owner("SMITH, JOHN")
    assert not is_hbg_public_owner(None)


def test_geo_feature_row_maps_name_and_market() -> None:
    from lotscope.ingestion.loaders.hbg import _geo_feature_row

    feature = ArcGisFeature(id=3, geometry=_GEOMETRY_4326, properties={"District": "Shipoke"})
    row = _geo_feature_row(feature, "Shipoke", "city_municipal_hd")
    assert row is not None
    assert row["external_id"] == "hbg:3"
    assert row["name"] == "Shipoke"
    assert row["market_code"] == "hbg"
    assert row["source"] == "city_municipal_hd"


def test_geo_feature_row_skips_without_name_or_id() -> None:
    from lotscope.ingestion.loaders.hbg import _geo_feature_row

    assert _geo_feature_row(ArcGisFeature(id=None, geometry=_GEOMETRY_4326), "X", "s") is None
    assert _geo_feature_row(ArcGisFeature(id=1, geometry=_GEOMETRY_4326), None, "s") is None
