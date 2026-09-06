from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.api.app import create_app
from lotscope.api.deps import get_current_user, get_session

pytestmark = pytest.mark.integration


def _app(db_session: AsyncSession, *, tier: str = "pro") -> FastAPI:
    app = create_app()

    async def _session() -> Any:
        yield db_session

    def _user() -> Any:
        return SimpleNamespace(
            id=1,
            role="user",
            tier=tier,
            email="a@example.com",
            full_name="Ada Buyer",
            entity_name="ACME LLC",
            signer_name=None,
            signer_phone="215-555-0100",
            signer_email=None,
        )

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_current_user] = _user
    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def _seed_user(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO app_user (id, email, hashed_password) VALUES (1, 'a@example.com', 'x') "
            "ON CONFLICT (id) DO NOTHING"
        )
    )
    await db_session.flush()


async def _parcel(db_session: AsyncSession, local: str, *, buildable: bool) -> None:
    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, market_code, address) VALUES (:pn, 'phl', :addr)"),
        {"pn": f"phl:{local}", "addr": f"{local} MAIN ST"},
    )
    if buildable:
        from lotscope.zoning.seed import seed_zoning_standards

        await seed_zoning_standards(db_session)
        await db_session.execute(
            text(
                "INSERT INTO zoning_district (code, geom_local) VALUES ('RSA-5', "
                "ST_GeomFromText('POLYGON((-100 -100,-100 100,100 100,100 -100,-100 -100))', "
                "2272)) ON CONFLICT DO NOTHING"
            )
        )
        await db_session.execute(
            text(
                "UPDATE parcel SET lot_area_sqft = 1600, frontage_ft = 18, depth_ft = 90, "
                "market_value = 150000, base_zoning_code = 'RSA-5', is_vacant = TRUE, "
                "geom_local = ST_GeomFromText('POLYGON((0 0,0 10,10 10,10 0,0 0))', 2272), "
                "geom_4326 = ST_SetSRID(ST_MakePoint(-75.16, 39.93), 4326) "
                "WHERE parcel_number = :pn"
            ),
            {"pn": f"phl:{local}"},
        )
        # Comparable sales next door, so the offer has an underwritten number behind it
        # rather than a blank: this is the path the letter actually takes.
        for index, price in enumerate((240000, 250000, 260000, 255000, 245000), start=1):
            neighbour = f"phl:{local}-comp{index}"
            await db_session.execute(
                text(
                    "INSERT INTO parcel (parcel_number, market_code, address, is_vacant, "
                    "lot_area_sqft, base_zoning_code, geom_local, geom_4326) VALUES "
                    "(:pn, 'phl', :addr, FALSE, 1600, 'RSA-5', "
                    "ST_GeomFromText('POLYGON((0 0,0 10,10 10,10 0,0 0))', 2272), "
                    "ST_SetSRID(ST_MakePoint(-75.16, 39.93), 4326))"
                ),
                {"pn": neighbour, "addr": f"{index} COMP ST"},
            )
            await db_session.execute(
                text(
                    "INSERT INTO sale (parcel_number, document_id, document_type, sale_date, "
                    "sale_price) VALUES (:pn, :doc, 'DEED', current_date - 60, :price)"
                ),
                {"pn": neighbour, "doc": f"D{local}{index}", "price": price},
            )
    await db_session.flush()


async def test_offer_generates_pdf_and_logs_activity(db_session: AsyncSession) -> None:
    await _seed_user(db_session)
    await _parcel(db_session, "100", buildable=True)
    app = _app(db_session, tier="pro")
    async with _client(app) as client:
        resp = await client.post("/pipeline/100/offer", json={})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")

    kind = await db_session.scalar(
        text(
            "SELECT a.kind FROM deal_activity a JOIN deal d ON d.id = a.deal_id "
            "WHERE d.parcel_number = 'phl:100' AND a.kind = 'offer_generated'"
        )
    )
    assert kind == "offer_generated"


async def test_offer_missing_economics_returns_409(db_session: AsyncSession) -> None:
    await _parcel(db_session, "200", buildable=False)
    app = _app(db_session, tier="pro")
    async with _client(app) as client:
        resp = await client.post("/pipeline/200/offer", json={})
    assert resp.status_code == 409


async def test_offer_manual_price_without_economics(db_session: AsyncSession) -> None:
    await _seed_user(db_session)
    await _parcel(db_session, "200", buildable=False)
    app = _app(db_session, tier="pro")
    async with _client(app) as client:
        resp = await client.post("/pipeline/200/offer", json={"offer_price": 42000})
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF")
