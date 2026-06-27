from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.api.app import create_app
from lotscope.api.deps import get_app_settings, get_session
from lotscope.core.config import Settings
from lotscope.zoning.seed import seed_zoning_standards


def _app_with_session(session: AsyncSession) -> FastAPI:
    app = create_app()

    async def _override() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _override
    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def _setup_verdict_parcel(session: AsyncSession) -> None:
    await seed_zoning_standards(session)
    await session.execute(
        text(
            "INSERT INTO zoning_district (code, geom_2272) VALUES ('RSA-5', "
            "ST_GeomFromText('POLYGON((-100 -100,-100 100,100 100,100 -100,-100 -100))', 2272))"
        )
    )
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, owner, lot_area_sqft, frontage_ft, depth_ft, "
            "market_value, base_zoning_code, geom_2272) VALUES "
            "('000000001', 'Jane Doe', 1600, 18, 90, 150000, 'RSA-5', "
            "ST_GeomFromText('POLYGON((0 0,0 10,10 10,10 0,0 0))', 2272))"
        )
    )
    await session.execute(
        text(
            "INSERT INTO tax_status (parcel_number, is_delinquent, total_due, years_owed) "
            "VALUES ('000000001', true, 20000, 4)"
        )
    )
    await session.flush()


@pytest.mark.integration
async def test_parcel_detail_endpoint(db_session: AsyncSession) -> None:
    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, owner) VALUES ('000000001', 'Jane Doe')")
    )
    await db_session.flush()

    async with _client(_app_with_session(db_session)) as client:
        ok = await client.get("/parcels/000000001")
        missing = await client.get("/parcels/999999999")

    assert ok.status_code == 200
    assert ok.json()["owner"] == "Jane Doe"
    assert missing.status_code == 404
    assert missing.json()["error"] == "NotFoundError"


@pytest.mark.integration
async def test_verdict_refresh_then_read(db_session: AsyncSession) -> None:
    await _setup_verdict_parcel(db_session)
    app = _app_with_session(db_session)

    async with _client(app) as client:
        before = await client.get("/parcels/000000001/verdict")
        refreshed = await client.post("/parcels/000000001/verdict/refresh")
        after = await client.get("/parcels/000000001/verdict")

    assert before.status_code == 404
    assert refreshed.status_code == 200
    assert refreshed.json()["verdict_version"] == "v1"
    assert after.status_code == 200
    assert "RSA-5" in after.json()["summary"]


@pytest.mark.integration
async def test_comps_endpoint(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, lot_area_sqft, geom_2272) VALUES "
            "('000000001', 2000, ST_GeomFromText('POLYGON((0 0,0 5,5 5,5 0,0 0))', 2272))"
        )
    )
    await db_session.flush()

    async with _client(_app_with_session(db_session)) as client:
        resp = await client.get("/parcels/000000001/comps")

    assert resp.status_code == 200
    assert resp.json()["comp_count"] == 0


@pytest.mark.integration
async def test_comps_endpoint_validates_radius(db_session: AsyncSession) -> None:
    async with _client(_app_with_session(db_session)) as client:
        resp = await client.get("/parcels/000000001/comps", params={"radius_ft": -1})

    assert resp.status_code == 422
    assert resp.json()["error"] == "ValidationError"


async def test_layers_endpoint() -> None:
    app = create_app()

    def _settings() -> Settings:
        return Settings(_env_file=None, martin_url="http://martin.test:3000")

    app.dependency_overrides[get_app_settings] = _settings
    async with _client(app) as client:
        resp = await client.get("/layers")

    assert resp.status_code == 200
    layers = {layer["name"]: layer for layer in resp.json()["layers"]}
    assert "parcels" in layers
    assert layers["parcels"]["tile_url"] == "http://martin.test:3000/parcels_mvt/{z}/{x}/{y}"
