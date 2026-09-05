from collections.abc import AsyncIterator
from unittest import mock

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.security import create_access_token
from lotscope.api.app import create_app
from lotscope.api.deps import get_app_settings, get_session
from lotscope.core.config import Settings

pytestmark = pytest.mark.integration

_SECRET = "checkout-secret-key-that-is-long-enough"


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {"_env_file": None, "secret_key": _SECRET}
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _app(session: AsyncSession, settings: Settings) -> FastAPI:
    app = create_app()

    async def _override() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _override
    app.dependency_overrides[get_app_settings] = lambda: settings
    return app


async def _user(session: AsyncSession, email: str) -> int:
    await session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active, "
            "email_verified_at) VALUES (:e, 'x', 'user', 'user', true, now())"
        ),
        {"e": email},
    )
    await session.flush()
    return int(await session.scalar(text("SELECT id FROM app_user WHERE email=:e"), {"e": email}))


def _auth(settings: Settings, user_id: int) -> dict[str, str]:
    token = create_access_token(settings, subject=str(user_id), role="user")
    return {"Authorization": f"Bearer {token}"}


async def test_checkout_is_503_when_stripe_is_unconfigured(db_session: AsyncSession) -> None:
    settings = _settings()
    user_id = await _user(db_session, "unconfigured@example.com")
    app = _app(db_session, settings)

    with mock.patch("stripe.checkout.Session.create") as created:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/checkout",
                headers=_auth(settings, user_id),
                json={"sku": "packet", "object_ref": "1"},
            )

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "billing_unconfigured"
    assert "Nothing was charged" in body["detail"]
    created.assert_not_called()

    rows = await db_session.scalar(text("SELECT count(*) FROM purchase"))
    assert rows == 0


async def test_a_missing_price_alone_is_enough_to_refuse(db_session: AsyncSession) -> None:
    settings = _settings(stripe_secret_key="sk_test_x", stripe_price_packet="price_packet")
    user_id = await _user(db_session, "halfconfigured@example.com")
    app = _app(db_session, settings)

    with mock.patch("stripe.checkout.Session.create") as created:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/checkout",
                headers=_auth(settings, user_id),
                json={"sku": "packet", "object_ref": "1"},
            )

    assert response.status_code == 503
    assert response.json()["code"] == "billing_unconfigured"
    created.assert_not_called()
    assert await db_session.scalar(text("SELECT count(*) FROM purchase")) == 0


async def test_checkout_creates_a_session_once_stripe_is_configured(
    db_session: AsyncSession,
) -> None:
    settings = _settings(
        stripe_secret_key="sk_test_x",
        stripe_price_packet="price_packet",
        stripe_price_diligence="price_diligence",
    )
    user_id = await _user(db_session, "configured@example.com")
    app = _app(db_session, settings)
    fake = mock.Mock(id="cs_configured", url="https://checkout.stripe.com/c/pay/cs_configured")

    with mock.patch("stripe.checkout.Session.create", return_value=fake):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/checkout",
                headers=_auth(settings, user_id),
                json={"sku": "packet", "object_ref": "1"},
            )

    assert response.status_code == 200
    assert response.json()["session_id"] == "cs_configured"
    assert await db_session.scalar(text("SELECT count(*) FROM purchase")) == 1


async def test_the_price_list_says_whether_purchasing_is_on(db_session: AsyncSession) -> None:
    settings = _settings()
    user_id = await _user(db_session, "prices@example.com")
    app = _app(db_session, settings)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/checkout/prices", headers=_auth(settings, user_id))

    body = response.json()
    assert body["configured"] is False
    assert body["skus"]["packet"]["amount_cents"] == 4900
    assert body["skus"]["diligence"]["amount_cents"] == 19900


async def _packet_for(session: AsyncSession, user_id: int, pdf_path: str) -> int:
    await session.execute(
        text(
            "INSERT INTO sale_packet (user_id, sale_date, status, pdf_path, generated_at) "
            "VALUES (:u, current_date + 7, 'ready', :p, now())"
        ),
        {"u": user_id, "p": pdf_path},
    )
    await session.flush()
    return int(await session.scalar(text("SELECT max(id) FROM sale_packet")))


async def test_a_comped_user_gets_the_packet(db_session: AsyncSession, tmp_path) -> None:  # type: ignore[no-untyped-def]
    settings = _settings()
    user_id = await _user(db_session, "comp-download@example.com")
    await db_session.execute(
        text("UPDATE app_user SET comp_until = now() + interval '30 days' WHERE id = :u"),
        {"u": user_id},
    )
    pdf = tmp_path / "packet.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")
    packet_id = await _packet_for(db_session, user_id, str(pdf))
    app = _app(db_session, settings)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/packets/{packet_id}/download", headers=_auth(settings, user_id)
        )

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")


async def test_an_uncomped_unpaid_user_is_402(db_session: AsyncSession, tmp_path) -> None:  # type: ignore[no-untyped-def]
    settings = _settings()
    user_id = await _user(db_session, "unpaid-download@example.com")
    pdf = tmp_path / "packet.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")
    packet_id = await _packet_for(db_session, user_id, str(pdf))
    app = _app(db_session, settings)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/packets/{packet_id}/download", headers=_auth(settings, user_id)
        )

    assert response.status_code == 402


async def test_a_packet_whose_pdf_is_unreachable_says_so_rather_than_crashing(
    db_session: AsyncSession,
) -> None:
    settings = _settings()
    user_id = await _user(db_session, "missing-pdf@example.com")
    await db_session.execute(
        text("UPDATE app_user SET comp_until = now() + interval '30 days' WHERE id = :u"),
        {"u": user_id},
    )
    packet_id = await _packet_for(db_session, user_id, "/nowhere/packet.pdf")
    app = _app(db_session, settings)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/packets/{packet_id}/download", headers=_auth(settings, user_id)
        )

    assert response.status_code == 404
    assert "not readable from this service" in response.json()["detail"]
