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
    get_summary_generator,
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

    async def sadd(self, key: str, *member: str) -> int:
        current = self.store.get(key)
        members = current if isinstance(current, set) else set()
        before = len(members)
        members.update(member)
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
    app.state.settings = Settings(
        _env_file=None, secret_key="test-secret-key-that-is-at-least-32-bytes-long"
    )

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
            "INSERT INTO zoning_district (code, geom_local) VALUES ('RSA-5', "
            "ST_GeomFromText('POLYGON((-100 -100,-100 100,100 100,100 -100,-100 -100))', 2272))"
        )
    )
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, owner, lot_area_sqft, frontage_ft, depth_ft, "
            "market_value, base_zoning_code, geom_local) VALUES "
            "('phl:000000001', 'Jane Doe', 1600, 18, 90, 150000, 'RSA-5', "
            "ST_GeomFromText('POLYGON((0 0,0 10,10 10,10 0,0 0))', 2272))"
        )
    )
    await session.execute(
        text(
            "INSERT INTO tax_status (parcel_number, is_delinquent, total_due, years_owed) "
            "VALUES ('phl:000000001', true, 20000, 4)"
        )
    )
    await session.flush()


@pytest.mark.integration
async def test_parcel_detail_endpoint(db_session: AsyncSession) -> None:
    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, owner) VALUES ('phl:000000001', 'Jane Doe')")
    )
    await db_session.flush()

    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        ok = await client.get("/parcels/phl:000000001")
        missing = await client.get("/parcels/999999999")

    assert ok.status_code == 200
    assert ok.json()["owner"] == "Jane Doe"
    assert missing.status_code == 404
    assert missing.json()["error"] == "NotFoundError"


@pytest.mark.integration
async def test_bare_and_prefixed_parcel_keys_resolve_identically(db_session: AsyncSession) -> None:
    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, owner) VALUES ('phl:056219700', 'Jane Doe')")
    )
    await db_session.flush()

    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        bare = await client.get("/parcels/056219700")
        prefixed = await client.get("/parcels/phl:056219700")

    assert bare.status_code == 200
    assert prefixed.status_code == 200
    assert bare.json() == prefixed.json()
    assert bare.json()["parcel_number"] == "phl:056219700"
    assert bare.json()["local_key"] == "056219700"
    assert bare.json()["market_code"] == "phl"


@pytest.mark.integration
async def test_variance_outlook_endpoint(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, base_zoning_code, zip_code) VALUES "
            "('phl:000000001', 'RSA5', '19123')"
        )
    )
    for index in range(12):
        await db_session.execute(
            text(
                "INSERT INTO parcel (parcel_number, base_zoning_code, zip_code) VALUES "
                "(:pn, 'RSA5', '19123')"
            ),
            {"pn": f"1000000{index:02d}"},
        )
        decision = "GRANTED" if index < 9 else "DENIED"
        await db_session.execute(
            text(
                "INSERT INTO zba_appeal (appeal_number, parcel_number, decision, decision_date) "
                "VALUES (:an, :pn, :decision, CURRENT_DATE)"
            ),
            {"an": f"A{index}", "pn": f"1000000{index:02d}", "decision": decision},
        )
    await db_session.flush()

    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        resp = await client.get("/parcels/phl:000000001/variance-outlook")

    assert resp.status_code == 200
    body = resp.json()
    assert body["parcel_number"] == "phl:000000001"
    assert body["district"] == "RSA5"
    assert body["decided"] == 12
    assert body["grant_rate"] == 0.75


@pytest.mark.integration
async def test_verdict_computes_on_read_and_refresh(db_session: AsyncSession) -> None:
    await _setup_verdict_parcel(db_session)
    app, _ = _authed_app(db_session)

    async with _client(app) as client:
        first = await client.get("/parcels/phl:000000001/verdict")
        refreshed = await client.post("/parcels/phl:000000001/verdict/refresh")
        after = await client.get("/parcels/phl:000000001/verdict")
        missing = await client.get("/parcels/999999999/verdict")

    assert first.status_code == 200
    assert first.json()["verdict_version"] == VERDICT_VERSION
    assert refreshed.status_code == 200
    assert after.status_code == 200
    assert "RSA-5" in after.json()["summary"]
    assert missing.status_code == 404


@pytest.mark.integration
async def test_verdict_recomputes_a_stale_stored_version_on_read(db_session: AsyncSession) -> None:
    await _setup_verdict_parcel(db_session)
    app, _ = _authed_app(db_session)

    async with _client(app) as client:
        await client.post("/parcels/phl:000000001/verdict/refresh")
        await db_session.execute(
            text(
                "UPDATE parcel_verdict SET verdict_version = 'v0', summary = 'stale' "
                "WHERE parcel_number = 'phl:000000001'"
            )
        )
        await db_session.commit()
        resp = await client.get("/parcels/phl:000000001/verdict")

    assert resp.status_code == 200
    assert resp.json()["verdict_version"] == VERDICT_VERSION
    assert resp.json()["summary"] != "stale"


@pytest.mark.integration
async def test_comps_endpoint(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, lot_area_sqft, geom_local) VALUES "
            "('phl:000000001', 2000, ST_GeomFromText('POLYGON((0 0,0 5,5 5,5 0,0 0))', 2272))"
        )
    )
    await db_session.flush()

    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        resp = await client.get("/parcels/phl:000000001/comps")

    assert resp.status_code == 200
    assert resp.json()["comp_count"] == 0


@pytest.mark.integration
async def test_comps_endpoint_validates_radius(db_session: AsyncSession) -> None:
    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        resp = await client.get("/parcels/phl:000000001/comps", params={"radius_ft": -1})

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
        text(
            "INSERT INTO parcel (parcel_number, base_zoning_code) VALUES ('phl:000000001', 'RSA-5')"
        )
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
            "/parcels/phl:000000001/ask", json={"question": "Can I build a house?"}
        )
        # repeat the same question — should be served from cache, not recomputed
        repeat = await client.post(
            "/parcels/phl:000000001/ask", json={"question": "Can I  build a HOUSE?"}
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
        resp = await client.post("/parcels/phl:000000001/ask", json={"question": "Hi?"})
    assert resp.status_code == 401


@pytest.mark.integration
async def test_ask_endpoint_enforces_tier_quota(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, base_zoning_code) VALUES ('phl:000000001', 'RSA-5')"
        )
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
        resp = await client.post("/parcels/phl:000000001/ask", json={"question": "Anything?"})

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
            text(f"INSERT INTO parcel (parcel_number, owner) VALUES ('phl:00000000{index}', 'O')")
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
            "VALUES ('phl:000000001', 'OWNER', '1 A ST', '99 ZZ AVE, NEW YORK NY', true)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO tax_status (parcel_number, is_delinquent, total_due, years_owed, "
            "in_sheriff_sale) VALUES ('phl:000000001', true, 25000, 5, true)"
        )
    )
    await db_session.flush()
    await recompute_distress(db_session, ["phl:000000001"])

    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        resp = await client.get("/leads?min_score=30")

    assert resp.status_code == 200
    body = resp.json()
    assert body["tier"] == "free"
    assert body["limit"] == 8
    assert body["leads"][0]["parcel_number"] == "phl:000000001"
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
            "VALUES ('phl:000000001', 'OWNER', '1 A ST', '99 ZZ AVE, NEW YORK NY', true)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO tax_status (parcel_number, is_delinquent, total_due, years_owed, "
            "in_sheriff_sale) VALUES ('phl:000000001', true, 25000, 5, true)"
        )
    )
    await db_session.flush()
    await recompute_distress(db_session, ["phl:000000001"])

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
async def test_pipeline_export_is_blocked_for_free_tier(db_session: AsyncSession) -> None:
    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        resp = await client.get("/pipeline/export")
    assert resp.status_code == 429


@pytest.mark.integration
async def test_pipeline_export_streams_csv_for_paid_tier(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO app_user (id, email, hashed_password, role, tier, is_active) "
            "VALUES (1, 'member@example.com', 'x', 'user', 'pro', true)"
        )
    )
    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, address) VALUES ('phl:000000001', '1 A ST')")
    )
    await db_session.execute(
        text(
            "INSERT INTO deal (user_id, parcel_number, stage, target_price, next_action, "
            "stage_entered_at) VALUES (1, 'phl:000000001', 'offer', 120000, 'Call owner', now())"
        )
    )
    await db_session.flush()

    app, _ = _authed_app(db_session)
    app.dependency_overrides[get_current_user] = _fake_pro_user
    async with _client(app) as client:
        resp = await client.get("/pipeline/export")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    body = resp.text
    assert "opportunity_score" in body.splitlines()[0]
    assert "phl:000000001" in body
    assert "Call owner" in body
    assert "Fair Housing" in body


@pytest.mark.integration
async def test_outreach_letters_blocked_for_free_tier(db_session: AsyncSession) -> None:
    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        resp = await client.post(
            "/outreach/letters", json={"from_name": "Sam", "from_contact": "555-0100"}
        )
    assert resp.status_code == 429


@pytest.mark.integration
async def test_outreach_letters_streams_pdf_for_paid_tier(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, owner, address, mailing_address, is_vacant) "
            "VALUES ('phl:000000001', 'OWNER', '1 A ST', '99 ZZ AVE, NEW YORK NY', true)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO tax_status (parcel_number, is_delinquent, total_due, years_owed, "
            "in_sheriff_sale) VALUES ('phl:000000001', true, 25000, 5, true)"
        )
    )
    await db_session.flush()
    await recompute_distress(db_session, ["phl:000000001"])

    app, _ = _authed_app(db_session)
    app.dependency_overrides[get_current_user] = _fake_pro_user
    async with _client(app) as client:
        resp = await client.post(
            "/outreach/letters",
            json={"from_name": "Sam Buyer", "from_contact": "555-0100", "min_score": 30},
        )

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"


@pytest.mark.integration
async def test_outreach_watchlist_letters_streams_pdf_for_paid_tier(
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO app_user (id, email, hashed_password, role, tier, is_active) "
            "VALUES (1, 'wl@example.com', 'x', 'user', 'pro', true)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, owner, address, mailing_address) "
            "VALUES ('phl:000000001', 'OWNER', '1 A ST', '99 ZZ AVE, NEW YORK NY')"
        )
    )
    await db_session.execute(
        text("INSERT INTO saved_parcel (user_id, parcel_number) VALUES (1, 'phl:000000001')")
    )
    await db_session.flush()

    app, _ = _authed_app(db_session)
    app.dependency_overrides[get_current_user] = _fake_pro_user
    async with _client(app) as client:
        resp = await client.post(
            "/outreach/letters/watchlist",
            json={"from_name": "Sam Buyer", "from_contact": "555-0100"},
        )

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"


@pytest.mark.integration
async def test_outreach_saved_search_letters_streams_pdf_for_paid_tier(
    db_session: AsyncSession,
) -> None:
    from lotscope.savedsearch.schemas import SavedSearchCreate, SearchCriteria
    from lotscope.savedsearch.service import create_search

    await db_session.execute(
        text(
            "INSERT INTO app_user (id, email, hashed_password, role, tier, is_active) "
            "VALUES (1, 'ss@example.com', 'x', 'user', 'pro', true)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, address, base_zoning_code, is_vacant, "
            "is_city_owned, market_value, owner, mailing_address) "
            "VALUES ('phl:000000001', '1 A ST', 'RSA-5', true, false, 50000, 'OWNER', '99 ZZ AVE')"
        )
    )
    await db_session.flush()
    search = await create_search(
        db_session,
        1,
        SavedSearchCreate(name="Vacant", criteria=SearchCriteria(vacant_only=True)),
        limit=None,
    )

    app, _ = _authed_app(db_session)
    app.dependency_overrides[get_current_user] = _fake_pro_user
    async with _client(app) as client:
        resp = await client.post(
            f"/outreach/letters/saved-search/{search.id}",
            json={"from_name": "Sam Buyer", "from_contact": "555-0100"},
        )

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"


@pytest.mark.integration
async def test_outreach_watchlist_letters_blocked_for_free_tier(db_session: AsyncSession) -> None:
    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        resp = await client.post(
            "/outreach/letters/watchlist", json={"from_name": "Sam", "from_contact": "x"}
        )
    assert resp.status_code == 429


@pytest.mark.integration
async def test_outreach_letters_404_when_no_mailable_leads(db_session: AsyncSession) -> None:
    app, _ = _authed_app(db_session)
    app.dependency_overrides[get_current_user] = _fake_pro_user
    async with _client(app) as client:
        resp = await client.post(
            "/outreach/letters",
            json={"from_name": "Sam", "from_contact": "555-0100", "min_score": 99},
        )
    assert resp.status_code == 404


@pytest.mark.integration
async def test_skip_trace_is_unavailable_without_a_provider(db_session: AsyncSession) -> None:
    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, owner) VALUES ('phl:000000001', 'JANE DOE')")
    )
    await db_session.flush()
    app, _ = _authed_app(db_session)
    app.dependency_overrides[get_app_settings] = lambda: Settings(_env_file=None)
    async with _client(app) as client:
        resp = await client.post("/parcels/phl:000000001/skip-trace")
    assert resp.status_code == 503


@pytest.mark.integration
async def test_credits_endpoint_reads_ledger_balance(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO app_user (id, email, hashed_password, role, tier, is_active) "
            "VALUES (1, 'member@example.com', 'x', 'user', 'pro', true)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO credit_ledger (user_id, delta, reason, ref) "
            "VALUES (1, 100, 'pack_purchase', 'pay_x'), (1, -1, 'skiptrace_burn', 'OK1')"
        )
    )
    await db_session.flush()
    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        resp = await client.get("/credits")
    assert resp.status_code == 200
    assert resp.json()["balance"] == 99


@pytest.mark.integration
async def test_neighborhood_market_is_gated_for_free_tier(db_session: AsyncSession) -> None:
    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        resp = await client.get("/neighborhoods/market")
    assert resp.status_code == 429


@pytest.mark.integration
async def test_neighborhood_market_returns_stats_for_paid_tier(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO neighborhood (name, geom_local) "
            "VALUES ('Alpha', ST_GeomFromText('POLYGON((0 0,0 100,100 100,100 0,0 0))', 2272))"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, is_vacant, market_value, geom_local) VALUES "
            "('phl:000000001', true, 40000, "
            "ST_GeomFromText('POLYGON((10 10,10 12,12 12,12 10,10 10))', 2272))"
        )
    )
    await db_session.execute(
        text("INSERT INTO tax_status (parcel_number, is_delinquent) VALUES ('phl:000000001', true)")
    )
    await db_session.flush()

    app, _ = _authed_app(db_session)
    app.dependency_overrides[get_current_user] = _fake_pro_user
    async with _client(app) as client:
        resp = await client.get("/neighborhoods/market")

    assert resp.status_code == 200
    body = resp.json()
    assert body["totals"]["vacant_lots"] == 1
    assert body["totals"]["tax_delinquent"] == 1
    assert body["neighborhoods"][0]["name"] == "Alpha"


@pytest.mark.integration
async def test_feed_is_gated_for_free_tier(db_session: AsyncSession) -> None:
    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        resp = await client.get("/feed")
    assert resp.status_code == 429


@pytest.mark.integration
async def test_feed_lists_recent_events_for_paid_tier(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, owner, is_vacant) "
            "VALUES ('phl:000000001', 'O', true)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO parcel_event (parcel_number, dataset, code, severity) "
            "VALUES ('phl:000000001', 'tax_delinquency', 'delinquent', 'high')"
        )
    )
    await db_session.flush()

    app, _ = _authed_app(db_session)
    app.dependency_overrides[get_current_user] = _fake_pro_user
    async with _client(app) as client:
        resp = await client.get("/feed?days=1")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["summary"][0]["code"] == "delinquent"
    assert body["events"][0]["parcel_number"] == "phl:000000001"


@pytest.mark.integration
async def test_sheriff_sales_is_gated_for_free_tier(db_session: AsyncSession) -> None:
    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        resp = await client.get("/sheriff-sales")
    assert resp.status_code == 429


@pytest.mark.integration
async def test_sheriff_sales_ranked_by_bid_gap_for_paid_tier(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, owner) VALUES "
            "('phl:000000001', 'A'), ('phl:000000002', 'B')"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO parcel_verdict "
            "(parcel_number, verdict_version, max_allowable_offer, opportunity_score) VALUES "
            "('phl:000000001', 't', 50000, 80), ('phl:000000002', 't', 30000, 60)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO sheriff_sale "
            "(parcel_number, case_number, sale_date, status, opening_bid) VALUES "
            "('phl:000000001', 'BW-A', '2026-08-05', 'Open', 10000), "
            "('phl:000000002', 'BW-B', '2026-08-06', 'Open', 25000)"
        )
    )
    await db_session.flush()

    app, _ = _authed_app(db_session)
    app.dependency_overrides[get_current_user] = _fake_pro_user
    async with _client(app) as client:
        resp = await client.get("/sheriff-sales")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert [item["case_number"] for item in body["items"]] == ["BW-A", "BW-B"]
    assert body["items"][0]["bid_gap"] == 40000.0
    assert body["items"][0]["opportunity_score"] == 80
    assert body["market"] == "phl"
    assert body["label"] == "Sheriff sales"
    assert body["state"] == "live"
    assert body["note"] is None


@pytest.mark.integration
async def test_sheriff_sales_by_url_slug_returns_the_market_rows(db_session: AsyncSession) -> None:
    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, owner) VALUES ('phl:000000001', 'A')")
    )
    await db_session.execute(
        text(
            "INSERT INTO sheriff_sale "
            "(parcel_number, case_number, sale_date, status, opening_bid) VALUES "
            "('phl:000000001', 'BW-A', '2026-08-05', 'Open', 10000)"
        )
    )
    await db_session.flush()

    app, _ = _authed_app(db_session)
    app.dependency_overrides[get_current_user] = _fake_pro_user
    async with _client(app) as client:
        by_slug = await client.get("/sheriff-sales", params={"market": "philadelphia"})
        by_code = await client.get("/sheriff-sales", params={"market": "phl"})

    assert by_slug.status_code == 200
    assert by_slug.json() == by_code.json()
    assert by_slug.json()["total"] == 1
    assert by_slug.json()["market"] == "phl"
    assert by_slug.json()["state"] == "live"


@pytest.mark.integration
async def test_sheriff_calendar_reports_honest_empty_state(db_session: AsyncSession) -> None:
    app, _ = _authed_app(db_session)
    app.dependency_overrides[get_current_user] = _fake_pro_user
    async with _client(app) as client:
        resp = await client.get("/sheriff-sales")

    body = resp.json()
    assert body["total"] == 0
    assert body["state"] == "empty"
    assert "No upcoming sheriff sales" in body["note"]


@pytest.mark.integration
async def test_sheriff_calendar_ics_feed(db_session: AsyncSession) -> None:
    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, address) VALUES ('phl:000000001', '1 Main St')")
    )
    await db_session.execute(
        text(
            "INSERT INTO sheriff_sale "
            "(parcel_number, case_number, sale_date, status, opening_bid) VALUES "
            "('phl:000000001', 'BW-A', '2026-08-05', 'Open', 10000)"
        )
    )
    await db_session.flush()

    app, _ = _authed_app(db_session)
    app.dependency_overrides[get_current_user] = _fake_pro_user
    async with _client(app) as client:
        resp = await client.get("/sheriff-sales/calendar.ics")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/calendar")
    text_body = resp.text
    assert "BEGIN:VCALENDAR" in text_body
    assert "BEGIN:VEVENT" in text_body
    assert "DTSTART;VALUE=DATE:20260805" in text_body
    assert "UID:BW-A@parcelphl.online" in text_body


async def test_sheriff_calendar_ics_gated_for_free_tier(db_session: AsyncSession) -> None:
    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        resp = await client.get("/sheriff-sales/calendar.ics")
    assert resp.status_code == 429


@pytest.mark.integration
async def test_sheriff_calendar_tokenized_subscribe_roundtrip(db_session: AsyncSession) -> None:
    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, address) VALUES ('phl:000000001', '1 Main St')")
    )
    await db_session.execute(
        text(
            "INSERT INTO sheriff_sale "
            "(parcel_number, case_number, sale_date, status, opening_bid) VALUES "
            "('phl:000000001', 'BW-A', '2026-08-05', 'Open', 10000)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
            "VALUES ('pro@example.com', 'x', 'user', 'pro', true)"
        )
    )
    uid = await db_session.scalar(text("SELECT id FROM app_user WHERE email = 'pro@example.com'"))
    await db_session.flush()

    from lotscope.accounts.security import create_calendar_token

    settings = Settings(_env_file=None)
    app, _ = _authed_app(db_session)
    app.dependency_overrides[get_current_user] = _fake_pro_user
    app.dependency_overrides[get_app_settings] = lambda: settings
    async with _client(app) as client:
        sub = await client.get("/sheriff-sales/calendar/subscribe")
        assert sub.status_code == 200
        url = sub.json()["url"]
        assert url.endswith(".ics")

        token = create_calendar_token(settings, user_id=int(uid))
        feed = await client.get(f"/sheriff-sales/calendar/{token}.ics")
        assert feed.status_code == 200
        assert feed.headers["content-type"].startswith("text/calendar")
        assert "BEGIN:VEVENT" in feed.text

        bad = await client.get("/sheriff-sales/calendar/not-a-token.ics")
        assert bad.status_code == 404


@pytest.mark.integration
async def test_assemblage_top_is_gated_for_free_tier(db_session: AsyncSession) -> None:
    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        resp = await client.get("/assemblage/top")
    assert resp.status_code == 429


@pytest.mark.integration
async def test_assemblage_top_ranks_by_unit_unlock(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, address, base_zoning_code) VALUES "
            "('phl:000000001', '1 A ST', 'RM-1'), ('phl:000000002', '2 B ST', 'RSA-5')"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO parcel_assemblage "
            "(parcel_number, potential, candidate_count, unit_unlock, "
            "combined_lot_area_sqft, base_zoning_code, neighborhood) VALUES "
            "('phl:000000001', 'high', 2, 6, 5000, 'RM-1', 'Fishtown'), "
            "('phl:000000002', 'medium', 1, 1, 3000, 'RSA-5', 'Point Breeze')"
        )
    )
    await db_session.flush()

    app, _ = _authed_app(db_session)
    app.dependency_overrides[get_current_user] = _fake_pro_user
    async with _client(app) as client:
        top = await client.get("/assemblage/top")
        filtered = await client.get("/assemblage/top?zoning=RSA")

    assert top.status_code == 200
    body = top.json()
    assert body["total"] == 2
    assert [p["parcel_number"] for p in body["plays"]] == ["phl:000000001", "phl:000000002"]
    assert body["plays"][0]["unit_unlock"] == 6

    assert [p["parcel_number"] for p in filtered.json()["plays"]] == ["phl:000000002"]


@pytest.mark.integration
async def test_assemblage_top_zoning_filter_matches_resolved_only(
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel "
            "(parcel_number, address, base_zoning_code, resolved_zoning_code) VALUES "
            "('000000901', '1 A ST', '', 'RM')"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO parcel_assemblage "
            "(parcel_number, potential, candidate_count, unit_unlock, "
            "combined_lot_area_sqft, base_zoning_code, neighborhood) VALUES "
            "('000000901', 'high', 2, 6, 5000, '', 'Midtown')"
        )
    )
    await db_session.flush()

    app, _ = _authed_app(db_session)
    app.dependency_overrides[get_current_user] = _fake_pro_user
    async with _client(app) as client:
        filtered = await client.get("/assemblage/top?zoning=RM")

    assert filtered.status_code == 200
    body = filtered.json()
    assert body["total"] == 1
    assert [p["parcel_number"] for p in body["plays"]] == ["000000901"]
    assert body["plays"][0]["base_zoning_code"] == "RM"


@pytest.mark.integration
async def test_appeal_packet_download_requires_entitlement(db_session: AsyncSession) -> None:
    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, owner) VALUES ('phl:000000001', 'O')")
    )
    await db_session.flush()

    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        resp = await client.get("/parcels/phl:000000001/appeal-packet.pdf")
    assert resp.status_code == 403


@pytest.mark.integration
async def test_appeal_packet_redeem_requires_credit(db_session: AsyncSession) -> None:
    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, owner) VALUES ('phl:000000001', 'O')")
    )
    await db_session.flush()

    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        resp = await client.post("/parcels/phl:000000001/appeal-packet")
    assert resp.status_code == 429


@pytest.mark.integration
async def test_appeal_packet_redeem_then_download(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, owner, market_value) "
            "VALUES ('phl:000000001', 'O', 300000)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO app_user (id, email, hashed_password, role, tier, is_active) "
            "VALUES (1, 'member@example.com', 'x', 'user', 'investor', true)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO credit_ledger (user_id, delta, reason, ref) "
            "VALUES (1, 1, 'appeal_packet_grant', '2026-07')"
        )
    )
    await db_session.flush()

    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        redeem = await client.post("/parcels/phl:000000001/appeal-packet")
        download = await client.get("/parcels/phl:000000001/appeal-packet.pdf")

    assert redeem.status_code == 200
    assert redeem.json()["entitled"] is True
    assert redeem.json()["source"] == "grant"
    assert download.status_code == 200
    assert download.content[:4] == b"%PDF"


@pytest.mark.integration
async def test_watchlist_add_list_remove(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO app_user (id, email, hashed_password, role, tier, is_active) "
            "VALUES (1, 'member@example.com', 'x', 'user', 'free', true)"
        )
    )
    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, address) VALUES ('phl:000000001', '1 Main St')")
    )
    await db_session.flush()

    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        added = await client.post(
            "/watchlist", json={"parcel_number": "phl:000000001", "tags": ["flip"]}
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
        resp = await client.get("/parcels/phl:000000001/dossier")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "dossier-phl-000000001.pdf" in resp.headers["content-disposition"]
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
        text("INSERT INTO parcel (parcel_number, address) VALUES ('phl:000000001', '1 Main St')")
    )
    await db_session.flush()

    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        added = await client.post("/pipeline", json={"parcel_number": "phl:000000001"})
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


@pytest.mark.integration
async def test_mark_onboarded_sets_timestamp_and_is_idempotent(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO app_user (id, email, hashed_password, role, tier, is_active) "
            "VALUES (1, 'ob@example.com', 'x', 'user', 'free', true)"
        )
    )
    await db_session.flush()

    app = _app_with_session(db_session)

    async def _current() -> User:
        fetched = await db_session.get(User, 1)
        assert fetched is not None
        return fetched

    app.dependency_overrides[get_current_user] = _current

    async with _client(app) as client:
        first = await client.post("/auth/onboarded")
        assert first.status_code == 200
        first_at = first.json()["onboarded_at"]
        assert first_at is not None

        second = await client.post("/auth/onboarded")
        assert second.json()["onboarded_at"] == first_at

    stored = await db_session.scalar(text("SELECT onboarded_at FROM app_user WHERE id = 1"))
    assert stored is not None


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


def _founding_settings() -> Settings:
    return Settings(
        _env_file=None,
        stripe_secret_key="sk_test",
        stripe_webhook_secret="wh_test",
        stripe_price_pro_monthly="price_monthly",
        stripe_price_pro_annual="price_annual",
        stripe_price_pro_founding="price_founding",
        founding_cap=2,
        founding_cutoff="2099-12-31",
        founding_price_monthly_cents=4900,
    )


class _FakeGateway:
    def __init__(self, event: dict[str, Any] | None = None, founding_count: int = 0) -> None:
        self.event = event
        self.checkout_args: dict[str, Any] | None = None
        self.founding_count = founding_count

    async def create_customer(self, *, email: str, user_id: int) -> str:
        return "cus_test"

    async def count_active_subscriptions_for_price(self, *, price_id: str) -> int:
        return self.founding_count

    async def create_checkout_session(
        self, *, customer_id: str, price_id: str, success_url: str, cancel_url: str
    ) -> str:
        self.checkout_args = {"customer_id": customer_id, "price_id": price_id}
        return "https://checkout.test/session"

    async def create_appeal_packet_checkout_session(
        self,
        *,
        customer_id: str,
        price_id: str,
        parcel_number: str,
        success_url: str,
        cancel_url: str,
    ) -> str:
        self.checkout_args = {"price_id": price_id, "parcel_number": parcel_number}
        return "https://checkout.test/packet"

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


async def test_billing_plans_exposes_founding_offer_when_configured() -> None:
    app = create_app()
    app.dependency_overrides[get_app_settings] = _founding_settings
    app.dependency_overrides[get_optional_user] = lambda: None
    async with _client(app) as client:
        resp = await client.get("/billing/plans")

    offer = resp.json()["founding_offer"]
    assert offer == {"price_monthly_cents": 4900, "cutoff": "2099-12-31"}


async def test_billing_plans_has_no_founding_offer_by_default() -> None:
    app = create_app()
    app.dependency_overrides[get_app_settings] = _billing_settings
    app.dependency_overrides[get_optional_user] = lambda: None
    async with _client(app) as client:
        resp = await client.get("/billing/plans")

    assert resp.json()["founding_offer"] is None


@pytest.mark.integration
async def test_founding_checkout_uses_founding_price_under_cap(db_session: AsyncSession) -> None:
    app = _app_with_session(db_session)
    gateway = _FakeGateway(founding_count=1)
    app.dependency_overrides[get_app_settings] = _founding_settings
    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_stripe_gateway] = lambda: gateway

    async with _client(app) as client:
        resp = await client.post("/billing/checkout", json={"founding": True})

    assert resp.status_code == 200
    assert gateway.checkout_args == {"customer_id": "cus_test", "price_id": "price_founding"}


@pytest.mark.integration
async def test_founding_checkout_rejected_when_cap_reached(db_session: AsyncSession) -> None:
    app = _app_with_session(db_session)
    gateway = _FakeGateway(founding_count=2)
    app.dependency_overrides[get_app_settings] = _founding_settings
    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_stripe_gateway] = lambda: gateway

    async with _client(app) as client:
        resp = await client.post("/billing/checkout", json={"founding": True})

    assert resp.status_code == 422
    assert gateway.checkout_args is None


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


class _FakeSummaryGenerator:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, *, system: str, user: str, schema: Any) -> dict[str, Any]:
        self.calls += 1
        return {"summary": "A vacant RSA-5 lot.", "is_informational": True}


@pytest.mark.integration
async def test_summary_dormant_without_api_key(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, base_zoning_code) VALUES ('phl:000000001', 'RSA-5')"
        )
    )
    await db_session.flush()

    app, _ = _authed_app(db_session)
    app.dependency_overrides[get_summary_generator] = lambda: _FakeSummaryGenerator()
    app.dependency_overrides[get_app_settings] = lambda: Settings(
        _env_file=None, secret_key="test-secret-key-that-is-at-least-32-bytes-long"
    )
    async with _client(app) as client:
        resp = await client.get("/parcels/phl:000000001/summary")
    assert resp.status_code == 404


@pytest.mark.integration
async def test_summary_endpoint_returns_and_caches(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, base_zoning_code) VALUES ('phl:000000001', 'RSA-5')"
        )
    )
    await db_session.flush()

    generator = _FakeSummaryGenerator()
    fake_redis = _FakeRedis()
    app = _app_with_session(db_session)
    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_redis] = lambda: fake_redis
    app.dependency_overrides[get_summary_generator] = lambda: generator
    app.dependency_overrides[get_app_settings] = lambda: Settings(
        _env_file=None,
        secret_key="test-secret-key-that-is-at-least-32-bytes-long",
        anthropic_api_key="test-key",
    )

    async with _client(app) as client:
        first = await client.get("/parcels/phl:000000001/summary")
        second = await client.get("/parcels/phl:000000001/summary")

    assert first.status_code == 200
    assert first.json()["summary"] == "A vacant RSA-5 lot."
    assert first.json()["parcel_number"] == "phl:000000001"
    assert first.json()["verdict_version"] == "none"
    assert first.json()["is_informational"] is True
    assert second.status_code == 200
    assert generator.calls == 1  # second call served from cache


class _FakeReportGenerator:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, *, system: str, user: str, schema: Any) -> dict[str, Any]:
        self.calls += 1
        return {
            "headline": "Underpriced by-right rowhouse lot.",
            "sections": [
                {"heading": "Overview", "body": "A vacant RSA-5 lot with by-right potential."},
                {"heading": "Risks", "body": "Tax delinquency is on record."},
            ],
            "recommendation": "Consider a direct offer near the max allowable offer.",
            "confidence": "medium",
            "is_informational": True,
        }


def _report_app(
    session: AsyncSession, generator: _FakeReportGenerator
) -> tuple[FastAPI, "_FakeRedis"]:
    fake_redis = _FakeRedis()
    app = _app_with_session(session)
    app.dependency_overrides[get_current_user] = _fake_pro_user
    app.dependency_overrides[get_redis] = lambda: fake_redis
    app.dependency_overrides[get_generator] = lambda: generator
    app.dependency_overrides[get_app_settings] = lambda: Settings(
        _env_file=None,
        secret_key="test-secret-key-that-is-at-least-32-bytes-long",
        anthropic_api_key="test-key",
    )
    return app, fake_redis


@pytest.mark.integration
async def test_report_is_gated_for_free_tier(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, base_zoning_code) VALUES ('phl:000000001', 'RSA-5')"
        )
    )
    await db_session.flush()

    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        resp = await client.get("/parcels/phl:000000001/report")
    assert resp.status_code == 429


@pytest.mark.integration
async def test_report_endpoint_returns_and_caches_for_paid_tier(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, base_zoning_code) VALUES ('phl:000000001', 'RSA-5')"
        )
    )
    await db_session.flush()

    generator = _FakeReportGenerator()
    app, _ = _report_app(db_session, generator)
    async with _client(app) as client:
        first = await client.get("/parcels/phl:000000001/report")
        second = await client.get("/parcels/phl:000000001/report")

    assert first.status_code == 200
    body = first.json()
    assert body["headline"] == "Underpriced by-right rowhouse lot."
    assert [section["heading"] for section in body["sections"]] == ["Overview", "Risks"]
    assert body["is_informational"] is True
    assert second.status_code == 200
    assert generator.calls == 1


@pytest.mark.integration
async def test_dossier_embeds_report_for_paid_tier(db_session: AsyncSession) -> None:
    await _setup_verdict_parcel(db_session)

    generator = _FakeReportGenerator()
    app, _ = _report_app(db_session, generator)
    async with _client(app) as client:
        resp = await client.get("/parcels/phl:000000001/dossier")

    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"
    assert generator.calls == 1


@pytest.mark.integration
async def test_webhook_fulfills_appeal_packet_purchase(db_session: AsyncSession) -> None:
    user = User(
        email="buyer@example.com", hashed_password="x", tier="free", stripe_customer_id="cus_1"
    )
    db_session.add(user)
    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, owner) VALUES ('phl:000000001', 'O')")
    )
    await db_session.flush()

    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_1",
                "mode": "payment",
                "customer": "cus_1",
                "payment_intent": "pi_1",
                "metadata": {"product": "appeal_packet", "parcel_number": "phl:000000001"},
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
    entitled = await db_session.scalar(
        text(
            "SELECT source FROM appeal_packet "
            "WHERE user_id = :uid AND parcel_number = 'phl:000000001'"
        ),
        {"uid": user.id},
    )
    assert entitled == "purchase"


@pytest.mark.integration
async def test_envelope_endpoint_returns_extrudable_footprint(db_session: AsyncSession) -> None:
    await seed_zoning_standards(db_session)
    await db_session.execute(
        text(
            "INSERT INTO zoning_district (code, geom_local) VALUES ('RSA-5', "
            "ST_GeomFromText('POLYGON((-500 -500,-500 500,500 500,500 -500,-500 -500))', 2272))"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, lot_area_sqft, frontage_ft, depth_ft, "
            "base_zoning_code, geom_local) VALUES ('phl:000000001', 6000, 60, 100, 'RSA-5', "
            "ST_GeomFromText('POLYGON((0 0,0 100,60 100,60 0,0 0))', 2272))"
        )
    )
    await db_session.flush()

    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        resp = await client.get("/parcels/phl:000000001/envelope")

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


_AREA_REQUEST = {
    "market": "philadelphia",
    "center": {"lng": -75.14, "lat": 39.99},
    "radius_m": 150,
    "limit": 2,
}


@pytest.mark.asyncio
async def test_search_does_not_disclose_owners_to_anonymous_callers(
    db_session: AsyncSession,
) -> None:
    app = _app_with_session(db_session)
    async with _client(app) as client:
        text_search = await client.get("/search?q=fairhill&market=philadelphia")
        area_search = await client.post("/search/area", json=_AREA_REQUEST)
    assert text_search.status_code == 401
    assert area_search.status_code == 401


@pytest.mark.asyncio
async def test_search_still_serves_a_signed_in_member(db_session: AsyncSession) -> None:
    app, _ = _authed_app(db_session)
    async with _client(app) as client:
        text_search = await client.get("/search?q=fairhill&market=philadelphia")
        area_search = await client.post("/search/area", json=_AREA_REQUEST)
    assert text_search.status_code == 200
    assert area_search.status_code == 200


@pytest.mark.asyncio
async def test_area_search_stops_disclosing_once_the_daily_parcel_quota_is_spent(
    db_session: AsyncSession,
) -> None:
    from lotscope.accounts.usage import area_search_key

    app, redis = _authed_app(db_session)
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    redis.store[area_search_key(1, today)] = {f"phl:{n}" for n in range(10_000)}

    async with _client(app) as client:
        response = await client.post("/search/area", json=_AREA_REQUEST)

    assert response.status_code == 429
    assert "limit" in response.json()["detail"].lower()
