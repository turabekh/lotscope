from typing import cast

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.verdict import cache
from lotscope.verdict.service import compute_verdict, get_verdict
from lotscope.zoning.seed import seed_zoning_standards

pytestmark = pytest.mark.integration


class _FakeRedis:
    """Enough Redis to hold one string per key, and to count the reads that hit it."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.hits = 0

    async def get(self, key: str) -> str | None:
        value = self.store.get(key)
        if value is not None:
            self.hits += 1
        return value

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value

    async def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            if self.store.pop(key, None) is not None:
                removed += 1
        return removed


async def _setup_parcel(session: AsyncSession) -> None:
    await seed_zoning_standards(session)
    await session.execute(
        text(
            "INSERT INTO zoning_district (code, geom_local) VALUES ('RSA-5', "
            "ST_GeomFromText('POLYGON((-100 -100,-100 100,100 100,100 -100,-100 -100))', 2272))"
        )
    )
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, lot_area_sqft, frontage_ft, depth_ft, "
            "market_value, base_zoning_code, geom_local) VALUES "
            "('000000001', 1600, 18, 90, 150000, 'RSA-5', "
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


async def test_a_verdict_is_computed_from_the_inputs_as_they_stand(
    db_session: AsyncSession,
) -> None:
    await _setup_parcel(db_session)

    result = await compute_verdict(db_session, "000000001")

    assert result is not None
    assert result.can_build_by_right is True
    assert result.risk_score is not None
    assert result.risk_score > 0
    assert "RSA-5" in result.summary
    assert any(flag["code"] == "tax_delinquency" for flag in result.risk_flags)
    # Nothing was written: there is no table for a verdict to go stale in.
    assert await db_session.scalar(text("SELECT to_regclass('parcel_verdict')::text")) is None


async def test_computing_a_verdict_for_a_parcel_we_do_not_hold_returns_nothing(
    db_session: AsyncSession,
) -> None:
    assert await compute_verdict(db_session, "999999999") is None


async def test_a_second_read_of_unchanged_inputs_comes_from_the_cache(
    db_session: AsyncSession,
) -> None:
    await _setup_parcel(db_session)
    redis = _FakeRedis()

    first = await get_verdict(db_session, "000000001", redis=cast(Redis, redis))
    second = await get_verdict(db_session, "000000001", redis=cast(Redis, redis))

    assert first is not None
    assert second is not None
    assert redis.hits == 1
    assert second.computed_at == first.computed_at  # the same computation, not a new one
    assert second.summary == first.summary


async def test_a_changed_violation_changes_the_verdict_with_no_job(
    db_session: AsyncSession,
) -> None:
    await _setup_parcel(db_session)
    redis = _FakeRedis()

    before = await get_verdict(db_session, "000000001", redis=cast(Redis, redis))
    assert before is not None
    assert not any(flag["code"].startswith("unsafe") for flag in before.risk_flags)

    await db_session.execute(
        text(
            "INSERT INTO li_event (parcel_number, external_id, event_type, status, "
            "case_status, event_date, description, is_unsafe, is_imminently_dangerous) VALUES "
            "('000000001', 'li-1', 'violation', 'OPEN', 'IN VIOLATION', current_date, "
            "'Unsafe structure', true, true)"
        )
    )
    await db_session.flush()

    after = await get_verdict(db_session, "000000001", redis=cast(Redis, redis))

    assert after is not None
    # A new input means a new fingerprint, so the cached copy cannot answer for it.
    assert after.risk_flags != before.risk_flags
    assert after.computed_at > before.computed_at


async def test_the_fingerprint_moves_when_an_input_row_does(db_session: AsyncSession) -> None:
    await _setup_parcel(db_session)

    before = await cache.input_fingerprint(db_session, "000000001", git_sha="abc123")
    await db_session.execute(
        text(
            "UPDATE tax_status SET total_due = 21000, updated_at = now() + interval '1 second' "
            "WHERE parcel_number = '000000001'"
        )
    )
    await db_session.flush()
    after = await cache.input_fingerprint(db_session, "000000001", git_sha="abc123")

    assert before is not None
    assert after is not None
    assert before != after


async def test_the_fingerprint_moves_when_the_code_does(db_session: AsyncSession) -> None:
    await _setup_parcel(db_session)

    # The same inputs read by different code are a different verdict, so a deploy has to
    # miss rather than serve yesterday's answer.
    old_code = await cache.input_fingerprint(db_session, "000000001", git_sha="abc123")
    new_code = await cache.input_fingerprint(db_session, "000000001", git_sha="def456")

    assert old_code != new_code


async def test_a_parcel_we_do_not_hold_has_no_fingerprint(db_session: AsyncSession) -> None:
    assert await cache.input_fingerprint(db_session, "999999999", git_sha="abc123") is None


async def test_invalidating_drops_the_entries_for_the_parcels_named(
    db_session: AsyncSession,
) -> None:
    await _setup_parcel(db_session)
    redis = _FakeRedis()
    await get_verdict(db_session, "000000001", redis=cast(Redis, redis))
    assert cache.cache_key("000000001") in redis.store

    dropped = await cache.invalidate_parcels(
        cast(Redis, redis), ["000000001", "000000001", "999999999"]
    )

    assert dropped == 1
    assert redis.store == {}
