import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.errors import ValidationError
from lotscope.skiptrace.provider import SkipTraceContacts
from lotscope.skiptrace.service import trace_owner

pytestmark = pytest.mark.integration


class _FakeProvider:
    name = "fake"

    def __init__(self, phones: list[str], emails: list[str]) -> None:
        self._contacts = SkipTraceContacts(phones=phones, emails=emails)
        self.calls = 0

    async def trace(self, *, owner: str | None, mailing_address: str | None) -> SkipTraceContacts:
        self.calls += 1
        return self._contacts


async def _add_user(session: AsyncSession, user_id: int) -> None:
    await session.execute(
        text(
            "INSERT INTO app_user (id, email, hashed_password, role, tier, is_active) "
            "VALUES (:id, :email, 'x', 'user', 'pro', true)"
        ),
        {"id": user_id, "email": f"u{user_id}@example.com"},
    )


async def _add_parcel(
    session: AsyncSession, parcel_number: str, *, owner: str | None, market: str = "phl"
) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, owner, mailing_address, market_code) "
            "VALUES (:pn, :owner, '1 MAIN ST', :market)"
        ),
        {"pn": parcel_number, "owner": owner, "market": market},
    )


async def test_a_trace_hits_the_provider_and_caches_the_result(
    db_session: AsyncSession,
) -> None:
    await _add_user(db_session, 1)
    await _add_parcel(db_session, "phl:1", owner="ACME LLC")
    await db_session.flush()
    provider = _FakeProvider(["215-555-0100"], ["owner@example.com"])

    first = await trace_owner(db_session, provider, 1, "phl:1")

    assert first.cached is False
    assert provider.calls == 1
    assert first.contacts.phones == ["215-555-0100"]


async def test_a_second_trace_of_the_same_owner_comes_from_cache(
    db_session: AsyncSession,
) -> None:
    await _add_user(db_session, 1)
    await _add_parcel(db_session, "phl:1", owner="ACME LLC")
    await db_session.flush()
    provider = _FakeProvider(["215-555-0100"], [])

    await trace_owner(db_session, provider, 1, "phl:1")
    second = await trace_owner(db_session, provider, 1, "phl:1")

    assert second.cached is True
    assert provider.calls == 1


async def test_another_user_also_reads_the_cache_rather_than_paying_again(
    db_session: AsyncSession,
) -> None:
    await _add_user(db_session, 1)
    await _add_user(db_session, 2)
    await _add_parcel(db_session, "phl:1", owner="ACME LLC")
    await db_session.flush()
    provider = _FakeProvider(["215-555-0100"], [])

    await trace_owner(db_session, provider, 1, "phl:1")
    other = await trace_owner(db_session, provider, 2, "phl:1")

    assert other.cached is True
    assert provider.calls == 1


async def test_missing_owner_key_raises(db_session: AsyncSession) -> None:
    await _add_user(db_session, 1)
    await _add_parcel(db_session, "phl:2", owner=None)
    await db_session.flush()

    with pytest.raises(ValidationError):
        await trace_owner(db_session, _FakeProvider([], []), 1, "phl:2")
