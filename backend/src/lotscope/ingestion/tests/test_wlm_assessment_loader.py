import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import Settings
from lotscope.ingestion.arcgis import ArcGisClient, ArcGisFeature
from lotscope.ingestion.loaders.wlm import (
    load_wlm_assessment,
    to_wlm_assessment_row,
    wilmington_parcels_layer_url,
)
from lotscope.ingestion.models import DatasetFreshness

_ATTRS = {
    "PRCLID": "2601320063",
    "OWNER": "HUDSON ALAN JOHN",
    "OWNRADD1": "1908 NORTH UNION STREET",
    "OWNRADD2": " ",
    "ASMTLAND": 6600,
    "ASMTSTRT": 33400,
    "PROP_CLASS": "011",
}

_LAYER_URL = "https://services.arcgis.com/hQ3wdpbjO3fPf612/arcgis/rest/services/LUP/FeatureServer/0"


def test_layer_url_builder_appends_service_path() -> None:
    url = wilmington_parcels_layer_url(
        "https://services.arcgis.com/hQ3wdpbjO3fPf612/arcgis/rest/services"
    )
    assert url.endswith("/LUP_Map_w_RISE_STAR_Bldg_Code_Enf_and_DDD_WFL1/FeatureServer/0")


def test_to_wlm_assessment_row_maps_owner_values_and_market() -> None:
    row = to_wlm_assessment_row(ArcGisFeature(properties=_ATTRS))
    assert row is not None
    assert row["parcel_number"] == "wlm:2601320063"
    assert row["owner"] == "HUDSON ALAN JOHN"
    assert row["mailing_address"] == "1908 NORTH UNION STREET"
    assert row["category"] == "011"
    assert row["land_value"] == 6600.0
    assert row["improvement_value"] == 33400.0
    assert row["market_value"] == 40000.0


def test_to_wlm_assessment_row_skips_without_key_and_zeroes_are_null() -> None:
    assert to_wlm_assessment_row(ArcGisFeature(properties={"PRCLID": None})) is None
    row = to_wlm_assessment_row(ArcGisFeature(properties={"PRCLID": "2601320063", "ASMTLAND": 0}))
    assert row is not None
    assert row["land_value"] is None
    assert row["market_value"] is None


class _AssessmentHandler:
    def __init__(self) -> None:
        self.calls = 0
        self.return_geometry: str | None = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.return_geometry = request.url.params.get("returnGeometry")
        self.calls += 1
        if self.calls > 1:
            return httpx.Response(200, json={"type": "FeatureCollection", "features": []})
        return httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [{"type": "Feature", "geometry": None, "properties": _ATTRS}],
            },
        )


def _settings() -> Settings:
    return Settings(_env_file=None, http_backoff_seconds=0.0)


@pytest.mark.integration
async def test_load_wlm_assessment_writes_owner_values_and_computes_owner_key(
    db_session: AsyncSession,
) -> None:
    handler = _AssessmentHandler()
    async with ArcGisClient(_settings(), transport=httpx.MockTransport(handler)) as arcgis:
        total = await load_wlm_assessment(db_session, arcgis, parcels_layer_url=_LAYER_URL)
    await db_session.flush()

    assert total == 1
    assert handler.return_geometry == "false"

    row = (
        await db_session.execute(
            text(
                "SELECT owner, owner_key, land_value, improvement_value, market_value, "
                "category, market_code FROM parcel WHERE parcel_number = :pn"
            ),
            {"pn": "wlm:2601320063"},
        )
    ).one()
    assert row[0] == "HUDSON ALAN JOHN"
    assert row[1] is not None
    assert float(row[2]) == 6600.0
    assert float(row[3]) == 33400.0
    assert float(row[4]) == 40000.0
    assert row[5] == "011"
    assert row[6] == "wlm"

    fresh = await db_session.get(DatasetFreshness, ("wlm", "wilmington_assessment"))
    assert fresh is not None
    assert fresh.status == "success"


@pytest.mark.integration
async def test_wlm_assessment_composes_onto_geometry_without_clobbering_it(
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel "
            "(parcel_number, market_code, coverage, lot_area_source, geom_local) "
            "VALUES ('wlm:2601320063', 'wlm', 'full', 'geometry', "
            "ST_SetSRID(ST_GeomFromText('POLYGON((614000 642000,614000 642100,"
            "614100 642100,614100 642000,614000 642000))'), 2235))"
        )
    )
    await db_session.flush()

    async with ArcGisClient(
        _settings(), transport=httpx.MockTransport(_AssessmentHandler())
    ) as arcgis:
        await load_wlm_assessment(db_session, arcgis, parcels_layer_url=_LAYER_URL)
    await db_session.flush()

    row = (
        await db_session.execute(
            text(
                "SELECT owner, ST_SRID(geom_local), lot_area_source "
                "FROM parcel WHERE parcel_number = :pn"
            ),
            {"pn": "wlm:2601320063"},
        )
    ).one()
    assert row[0] == "HUDSON ALAN JOHN"
    assert row[1] == 2235
    assert row[2] == "geometry"
