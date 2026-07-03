from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.accounts.usage import ask_usage_key, parcel_view_key
from lotscope.ai.models import EMBEDDING_DIMENSIONS
from lotscope.ai.retrieval import add_document
from lotscope.api.app import create_app
from lotscope.api.deps import (
    get_app_settings,
    get_current_user,
    get_embedder,
    get_generator,
    get_optional_user,
    get_redis,
    get_session,
    get_stripe_gateway,
)
from lotscope.core.config import Settings
from lotscope.distress.service import recompute_distress
from lotscope.verdict.composition import VERDICT_VERSION
from lotscope.zoning.seed import seed_zoning_standards


def _fake_user() -> User:
    return User(
        id=1,
        email="member@example.com",
        hashed_password="x",
        full_name=None,
        role="user",
        tier="free",
        is_active=True,
        digest_frequency="weekly",
        created_at=datetime.now(UTC),
    )


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, object] = {}

    async def get(self, key: str) -> object | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value

    async def incr(self, key: str) -> int:
        current = self.store.get(key, 0)
        value = (current if isinstance(current, int) else 0) + 1
        self.store[key] = value
        return value

    async def decr(self, key: str) -> int:
        current = self.store.get(key, 0)
        value = (current if isinstance(current, int) else 0) - 1
        self.store[key] = value
        return value

    async def expire(self, key: str, ttl: int) -> bool:
        return True

    async def sadd(self, key: str, member: str) -> int:
        current = self.store.get(key)
        members = current if isinstance(current, set) else set()
        before = len(members)
        members.add(member)
        self.store[key] = members
        return len(members) - before

    async def scard(self, key: str) -> int:
        current = self.store.get(key)
        return len(current) if isinstance(current, set) else 0

    async def sismember(self, key: str, member: str) -> bool:
        current = self.store.get(key)
        return isinstance(current, set) and member in current


def _app_with_session(session: AsyncSession) -> FastAPI:
    app = create_app()

    async def _override() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _override
    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def _authed_app(session: AsyncSession) -> tuple[FastAPI, "_FakeRedis"]:
    app = _app_with_session(session)
    redis = _FakeRedis()
    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_redis] = lambda: redis
    return app, redis


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

    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        ok = await client.get("/parcels/000000001")
        missing = await client.get("/parcels/999999999")

    assert ok.status_code == 200
    assert ok.json()["owner"] == "Jane Doe"
    assert missing.status_code == 404
    assert missing.json()["error"] == "NotFoundError"


@pytest.mark.integration
async def test_verdict_refresh_then_read(db_session: AsyncSession) -> None:
    await _setup_verdict_parcel(db_session)
    app, _ = _authed_app(db_session)

    async with _client(app) as client:
        before = await client.get("/parcels/000000001/verdict")
        refreshed = await client.post("/parcels/000000001/verdict/refresh")
        after = await client.get("/parcels/000000001/verdict")

    assert before.status_code == 404
    assert refreshed.status_code == 200
    assert refreshed.json()["verdict_version"] == VERDICT_VERSION
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

    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        resp = await client.get("/parcels/000000001/comps")

    assert resp.status_code == 200
    assert resp.json()["comp_count"] == 0


@pytest.mark.integration
async def test_comps_endpoint_validates_radius(db_session: AsyncSession) -> None:
    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        resp = await client.get("/parcels/000000001/comps", params={"radius_ft": -1})

    assert resp.status_code == 422
    assert resp.json()["error"] == "ValidationError"


class _FakeEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1)]


class _FakeGenerator:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, *, system: str, user: str, schema: Any) -> dict[str, Any]:
        self.calls += 1
        return {
            "answer": "Yes, by-right.",
            "citations": [{"source": "Title 14", "section": "14-701"}],
            "confidence": "high",
        }


@pytest.mark.integration
async def test_ask_endpoint(db_session: AsyncSession) -> None:
    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, base_zoning_code) VALUES ('000000001', 'RSA-5')")
    )
    await add_document(
        db_session,
        source="title14",
        section="14-701",
        content="RSA-5 minimum lot area is 1,440 sqft.",
        embedding=[1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1),
    )
    await db_session.flush()

    app = _app_with_session(db_session)
    generator = _FakeGenerator()
    fake_redis = _FakeRedis()
    app.dependency_overrides[get_embedder] = _FakeEmbedder
    app.dependency_overrides[get_generator] = lambda: generator
    app.dependency_overrides[get_redis] = lambda: fake_redis
    app.dependency_overrides[get_current_user] = _fake_user

    async with _client(app) as client:
        resp = await client.post(
            "/parcels/000000001/ask", json={"question": "Can I build a house?"}
        )
        # repeat the same question — should be served from cache, not recomputed
        repeat = await client.post(
            "/parcels/000000001/ask", json={"question": "Can I  build a HOUSE?"}
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["citations"][0]["section"] == "14-701"
    assert body["is_informational"] is True
    assert repeat.status_code == 200
    assert repeat.json() == body
    assert generator.calls == 1


@pytest.mark.integration
async def test_ask_endpoint_requires_authentication(db_session: AsyncSession) -> None:
    app = _app_with_session(db_session)
    app.dependency_overrides[get_app_settings] = lambda: Settings(
        _env_file=None, secret_key="test-secret-key-that-is-at-least-32-bytes-long"
    )
    app.dependency_overrides[get_embedder] = _FakeEmbedder
    app.dependency_overrides[get_generator] = lambda: _FakeGenerator()
    app.dependency_overrides[get_redis] = lambda: _FakeRedis()
    async with _client(app) as client:
        resp = await client.post("/parcels/000000001/ask", json={"question": "Hi?"})
    assert resp.status_code == 401


@pytest.mark.integration
async def test_ask_endpoint_enforces_tier_quota(db_session: AsyncSession) -> None:
    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, base_zoning_code) VALUES ('000000001', 'RSA-5')")
    )
    await db_session.flush()

    app = _app_with_session(db_session)
    generator = _FakeGenerator()
    fake_redis = _FakeRedis()
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    fake_redis.store[ask_usage_key(1, today)] = 10  # free tier limit already reached
    app.dependency_overrides[get_embedder] = _FakeEmbedder
    app.dependency_overrides[get_generator] = lambda: generator
    app.dependency_overrides[get_redis] = lambda: fake_redis
    app.dependency_overrides[get_current_user] = _fake_user

    async with _client(app) as client:
        resp = await client.post("/parcels/000000001/ask", json={"question": "Anything?"})

    assert resp.status_code == 429
    assert resp.json()["error"] == "QuotaExceededError"
    assert generator.calls == 0


@pytest.mark.integration
async def test_usage_endpoint_reports_tier_and_remaining(db_session: AsyncSession) -> None:
    app = _app_with_session(db_session)
    fake_redis = _FakeRedis()
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    fake_redis.store[ask_usage_key(1, today)] = 3
    app.dependency_overrides[get_redis] = lambda: fake_redis
    app.dependency_overrides[get_current_user] = _fake_user

    fake_redis.store[parcel_view_key(1, today)] = {"a", "b"}

    async with _client(app) as client:
        resp = await client.get("/auth/usage")

    assert resp.status_code == 200
    body = resp.json()
    assert body["tier"] == "free"
    assert body["ask"] == {"limit": 10, "used": 3, "remaining": 7}
    assert body["parcel_views"] == {"limit": 4, "used": 2, "remaining": 2}


@pytest.mark.integration
async def test_parcel_detail_enforces_free_view_quota(db_session: AsyncSession) -> None:
    for index in range(5):
        await db_session.execute(
            text(f"INSERT INTO parcel (parcel_number, owner) VALUES ('00000000{index}', 'O')")
        )
    await db_session.flush()

    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        statuses = [
            (await client.get(f"/parcels/00000000{index}")).status_code for index in range(5)
        ]
        repeat = await client.get("/parcels/000000000")

    assert statuses[:4] == [200, 200, 200, 200]
    assert statuses[4] == 429  # fifth distinct parcel exceeds the free limit of 4
    assert repeat.status_code == 200  # re-opening an already-viewed parcel is free


@pytest.mark.integration
async def test_leads_endpoint_ranks_and_caps_by_tier(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, owner, address, mailing_address, is_vacant) "
            "VALUES ('000000001', 'OWNER', '1 A ST', '99 ZZ AVE, NEW YORK NY', true)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO tax_status (parcel_number, is_delinquent, total_due, years_owed, "
            "in_sheriff_sale) VALUES ('000000001', true, 25000, 5, true)"
        )
    )
    await db_session.flush()
    await recompute_distress(db_session, ["000000001"])

    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        resp = await client.get("/leads?min_score=30")

    assert resp.status_code == 200
    body = resp.json()
    assert body["tier"] == "free"
    assert body["limit"] == 8
    assert body["leads"][0]["parcel_number"] == "000000001"
    assert body["leads"][0]["score"] == 80


def _fake_pro_user() -> User:
    user = _fake_user()
    user.tier = "pro"
    return user


@pytest.mark.integration
async def test_leads_export_is_blocked_for_free_tier(db_session: AsyncSession) -> None:
    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        resp = await client.get("/leads/export")
    assert resp.status_code == 429


@pytest.mark.integration
async def test_leads_export_streams_csv_for_paid_tier(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, owner, address, mailing_address, is_vacant) "
            "VALUES ('000000001', 'OWNER', '1 A ST', '99 ZZ AVE, NEW YORK NY', true)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO tax_status (parcel_number, is_delinquent, total_due, years_owed, "
            "in_sheriff_sale) VALUES ('000000001', true, 25000, 5, true)"
        )
    )
    await db_session.flush()
    await recompute_distress(db_session, ["000000001"])

    app, _ = _authed_app(db_session)
    app.dependency_overrides[get_current_user] = _fake_pro_user
    async with _client(app) as client:
        resp = await client.get("/leads/export?min_score=30")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    body = resp.text
    assert "mailing_address" in body.splitlines()[0]
    assert "99 ZZ AVE, NEW YORK NY" in body
    assert "Fair Housing" in body


@pytest.mark.integration
async def test_watchlist_add_list_remove(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO app_user (id, email, hashed_password, role, tier, is_active) "
            "VALUES (1, 'member@example.com', 'x', 'user', 'free', true)"
        )
    )
    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, address) VALUES ('000000001', '1 Main St')")
    )
    await db_session.flush()

    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        added = await client.post(
            "/watchlist", json={"parcel_number": "000000001", "tags": ["flip"]}
        )
        listed = await client.get("/watchlist")
        state = await client.get("/watchlist/000000001")
        removed = await client.delete("/watchlist/000000001")
        after = await client.get("/watchlist")

    assert added.status_code == 201
    assert listed.json()["used"] == 1
    assert listed.json()["limit"] == 25
    assert listed.json()["items"][0]["address"] == "1 Main St"
    assert state.json() == {"saved": True}
    assert removed.status_code == 204
    assert after.json()["used"] == 0


@pytest.mark.integration
async def test_dossier_endpoint_returns_pdf(db_session: AsyncSession) -> None:
    await _setup_verdict_parcel(db_session)
    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        resp = await client.get("/parcels/000000001/dossier")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "dossier-000000001.pdf" in resp.headers["content-disposition"]
    assert resp.content[:4] == b"%PDF"


@pytest.mark.integration
async def test_pipeline_add_move_and_remove(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO app_user (id, email, hashed_password, role, tier, is_active) "
            "VALUES (1, 'm@example.com', 'x', 'user', 'free', true)"
        )
    )
    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, address) VALUES ('000000001', '1 Main St')")
    )
    await db_session.flush()

    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        added = await client.post("/pipeline", json={"parcel_number": "000000001"})
        listed = await client.get("/pipeline")
        moved = await client.patch("/pipeline/000000001", json={"stage": "offer"})
        removed = await client.delete("/pipeline/000000001")
        after = await client.get("/pipeline")

    assert added.status_code == 201
    assert added.json()["stage"] == "lead"
    assert listed.json()["limit"] == 10
    assert listed.json()["deals"][0]["address"] == "1 Main St"
    assert moved.json()["stage"] == "offer"
    assert removed.status_code == 204
    assert after.json()["used"] == 0


@pytest.mark.integration
async def test_push_subscribe_and_vapid_key(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO app_user (id, email, hashed_password, role, tier, is_active) "
            "VALUES (1, 'm@example.com', 'x', 'user', 'free', true)"
        )
    )
    await db_session.flush()

    app = _app_with_session(db_session)
    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_app_settings] = lambda: Settings(_env_file=None)

    async with _client(app) as client:
        key = await client.get("/push/vapid-public-key")
        sub = await client.post(
            "/push/subscribe",
            json={"endpoint": "https://push/x", "keys": {"p256dh": "k", "auth": "a"}},
        )
        unsub = await client.post("/push/unsubscribe", json={"endpoint": "https://push/x"})

    assert key.status_code == 200
    assert key.json() == {"public_key": None}
    assert sub.status_code == 204
    assert unsub.status_code == 204
    remaining = await db_session.scalar(text("SELECT count(*) FROM push_subscription"))
    assert remaining == 0


@pytest.mark.integration
async def test_digest_preference_and_unsubscribe(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO app_user (id, email, hashed_password, role, tier, is_active, "
            "digest_frequency) VALUES (1, 'm@example.com', 'x', 'user', 'free', true, 'weekly')"
        )
    )
    await db_session.flush()

    settings = Settings(_env_file=None, secret_key="test-secret-key-test-secret-key-32")
    app = _app_with_session(db_session)
    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_app_settings] = lambda: settings

    async with _client(app) as client:
        pref = await client.patch("/auth/digest", json={"frequency": "daily"})
        assert pref.status_code == 200
        assert pref.json()["digest_frequency"] == "daily"

        from lotscope.accounts.security import create_unsubscribe_token

        token = create_unsubscribe_token(settings, user_id=1)
        unsub = await client.get(f"/digests/unsubscribe?token={token}")
        assert unsub.status_code == 200
        assert "unsubscribed" in unsub.text.lower()

    frequency = await db_session.scalar(text("SELECT digest_frequency FROM app_user WHERE id = 1"))
    assert frequency == "off"


async def test_basemap_session_unconfigured_returns_503() -> None:
    app = create_app()
    app.dependency_overrides[get_app_settings] = lambda: Settings(_env_file=None)
    app.dependency_overrides[get_redis] = lambda: _FakeRedis()

    async with _client(app) as client:
        resp = await client.get("/maps/basemap-session?map_type=satellite")

    assert resp.status_code == 503
    assert resp.json()["error"] == "ConfigurationError"


async def test_cors_allows_configured_origin() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


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


def _billing_settings() -> Settings:
    return Settings(
        _env_file=None,
        stripe_secret_key="sk_test",
        stripe_webhook_secret="wh_test",
        stripe_price_pro_monthly="price_monthly",
        stripe_price_pro_annual="price_annual",
    )


class _FakeGateway:
    def __init__(self, event: dict[str, Any] | None = None) -> None:
        self.event = event
        self.checkout_args: dict[str, Any] | None = None

    async def create_customer(self, *, email: str, user_id: int) -> str:
        return "cus_test"

    async def create_checkout_session(
        self, *, customer_id: str, price_id: str, success_url: str, cancel_url: str
    ) -> str:
        self.checkout_args = {"customer_id": customer_id, "price_id": price_id}
        return "https://checkout.test/session"

    async def create_portal_session(self, *, customer_id: str, return_url: str) -> str:
        return "https://portal.test/session"

    def parse_event(self, *, payload: bytes, signature: str) -> dict[str, Any]:
        assert self.event is not None
        return self.event


async def test_billing_plans_public_lists_catalog() -> None:
    app = create_app()
    app.dependency_overrides[get_app_settings] = _billing_settings
    app.dependency_overrides[get_optional_user] = lambda: None
    async with _client(app) as client:
        resp = await client.get("/billing/plans")

    assert resp.status_code == 200
    body = resp.json()
    tiers = [plan["tier"] for plan in body["plans"]]
    assert tiers == ["free", "pro", "investor", "enterprise"]
    assert all(plan["is_current"] is False for plan in body["plans"])
    assert body["contact_url"]


async def test_billing_plans_marks_current_tier() -> None:
    app = create_app()
    app.dependency_overrides[get_app_settings] = _billing_settings

    def _pro_user() -> User:
        user = _fake_user()
        user.tier = "pro"
        return user

    app.dependency_overrides[get_optional_user] = _pro_user
    async with _client(app) as client:
        resp = await client.get("/billing/plans")

    plans = {plan["tier"]: plan for plan in resp.json()["plans"]}
    assert plans["pro"]["is_current"] is True
    assert plans["free"]["is_current"] is False


@pytest.mark.integration
async def test_checkout_returns_session_url(db_session: AsyncSession) -> None:
    app = _app_with_session(db_session)
    gateway = _FakeGateway()
    app.dependency_overrides[get_app_settings] = _billing_settings
    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_stripe_gateway] = lambda: gateway

    async with _client(app) as client:
        resp = await client.post("/billing/checkout", json={"cadence": "annual"})

    assert resp.status_code == 200
    assert resp.json()["url"] == "https://checkout.test/session"
    assert gateway.checkout_args == {"customer_id": "cus_test", "price_id": "price_annual"}


async def test_portal_requires_existing_customer(db_session: AsyncSession) -> None:
    app = _app_with_session(db_session)
    app.dependency_overrides[get_app_settings] = _billing_settings
    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_stripe_gateway] = lambda: _FakeGateway()

    async with _client(app) as client:
        resp = await client.post("/billing/portal")

    assert resp.status_code == 422


@pytest.mark.integration
async def test_webhook_activates_pro_tier(db_session: AsyncSession) -> None:
    user = User(
        email="buyer@example.com",
        hashed_password="x",
        tier="free",
        stripe_customer_id="cus_1",
    )
    db_session.add(user)
    await db_session.flush()

    event = {
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_1",
                "customer": "cus_1",
                "status": "active",
                "items": {"data": [{"price": {"id": "price_monthly"}}]},
            }
        },
    }
    app = _app_with_session(db_session)
    app.dependency_overrides[get_app_settings] = _billing_settings
    app.dependency_overrides[get_stripe_gateway] = lambda: _FakeGateway(event)

    async with _client(app) as client:
        resp = await client.post(
            "/billing/webhook", content=b"{}", headers={"Stripe-Signature": "sig"}
        )

    assert resp.status_code == 200
    assert resp.json() == {"handled": True}
    await db_session.refresh(user)
    assert user.tier == "pro"
    assert user.subscription_status == "active"
    assert user.stripe_subscription_id == "sub_1"


@pytest.mark.integration
async def test_envelope_endpoint_returns_extrudable_footprint(db_session: AsyncSession) -> None:
    await seed_zoning_standards(db_session)
    await db_session.execute(
        text(
            "INSERT INTO zoning_district (code, geom_2272) VALUES ('RSA-5', "
            "ST_GeomFromText('POLYGON((-500 -500,-500 500,500 500,500 -500,-500 -500))', 2272))"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, lot_area_sqft, frontage_ft, depth_ft, "
            "base_zoning_code, geom_2272) VALUES ('000000001', 6000, 60, 100, 'RSA-5', "
            "ST_GeomFromText('POLYGON((0 0,0 100,60 100,60 0,0 0))', 2272))"
        )
    )
    await db_session.flush()

    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        resp = await client.get("/parcels/000000001/envelope")

    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is True
    assert body["district_code"] == "RSA-5"
    assert body["max_height_ft"] is not None
    assert body["estimated_floors"] is not None
    assert body["lot_footprint"]["type"] == "Polygon"
    assert body["buildable_footprint"]["type"] == "Polygon"
    assert body["buildable_area_sqft"] <= 6000
    assert any(source["source"] == "zoning_standard" for source in body["sources"])


async def test_webhook_requires_signature(db_session: AsyncSession) -> None:
    app = _app_with_session(db_session)
    app.dependency_overrides[get_app_settings] = _billing_settings
    app.dependency_overrides[get_stripe_gateway] = lambda: _FakeGateway()

    async with _client(app) as client:
        resp = await client.post("/billing/webhook", content=b"{}")

    assert resp.status_code == 422
