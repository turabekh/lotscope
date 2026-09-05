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


async def _parcel(db_session: AsyncSession, local: str, *, mao: float | None) -> None:
    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, market_code, address) VALUES (:pn, 'phl', :addr)"),
        {"pn": f"phl:{local}", "addr": f"{local} MAIN ST"},
    )
    if mao is not None:
        await db_session.execute(
            text(
                "INSERT INTO parcel_verdict "
                "(parcel_number, verdict_version, max_allowable_offer, risk_flags, sources) "
                "VALUES (:pn, 'v8', :mao, '[]'::jsonb, '[]'::jsonb)"
            ),
            {"pn": f"phl:{local}", "mao": mao},
        )
    await db_session.flush()


async def test_offer_generates_pdf_and_logs_activity(db_session: AsyncSession) -> None:
    await _seed_user(db_session)
    await _parcel(db_session, "100", mao=100000.0)
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
    await _parcel(db_session, "200", mao=None)
    app = _app(db_session, tier="pro")
    async with _client(app) as client:
        resp = await client.post("/pipeline/200/offer", json={})
    assert resp.status_code == 409


async def test_offer_manual_price_without_economics(db_session: AsyncSession) -> None:
    await _seed_user(db_session)
    await _parcel(db_session, "200", mao=None)
    app = _app(db_session, tier="pro")
    async with _client(app) as client:
        resp = await client.post("/pipeline/200/offer", json={"offer_price": 42000})
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF")
