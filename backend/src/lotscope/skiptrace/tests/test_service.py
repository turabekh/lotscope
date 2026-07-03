import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.errors import QuotaExceededError, ValidationError
from lotscope.skiptrace.models import REASON_INVESTOR_GRANT, REASON_PACK_PURCHASE
from lotscope.skiptrace.provider import SkipTraceContacts
from lotscope.skiptrace.service import credit_balance, grant_credits, trace_owner

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


async def _add_parcel(session: AsyncSession, parcel_number: str, *, owner: str | None) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, owner, mailing_address) "
            "VALUES (:pn, :owner, '1 MAIN ST')"
        ),
        {"pn": parcel_number, "owner": owner},
    )


async def test_grant_credits_is_idempotent_on_ref(db_session: AsyncSession) -> None:
    await _add_user(db_session, 1)
    await db_session.flush()
    assert await grant_credits(db_session, 1, 100, REASON_PACK_PURCHASE, "pay_1") is True
    assert await grant_credits(db_session, 1, 100, REASON_PACK_PURCHASE, "pay_1") is False
    assert await credit_balance(db_session, 1) == 100


async def test_trace_burns_one_credit_and_caches(db_session: AsyncSession) -> None:
    await _add_user(db_session, 1)
    await _add_parcel(db_session, "000000001", owner="JANE DOE")
    await grant_credits(db_session, 1, 5, REASON_PACK_PURCHASE, "pay_1")
    await db_session.flush()

    provider = _FakeProvider(["215-555-0100"], ["jane@example.com"])
    result = await trace_owner(db_session, provider, 1, "000000001")
    assert result.credits_spent == 1
    assert result.credits_remaining == 4
    assert result.contacts.phones == ["215-555-0100"]
    assert provider.calls == 1


async def test_second_trace_same_user_is_free_from_cache(db_session: AsyncSession) -> None:
    await _add_user(db_session, 1)
    await _add_parcel(db_session, "000000001", owner="JANE DOE")
    await grant_credits(db_session, 1, 5, REASON_PACK_PURCHASE, "pay_1")
    await db_session.flush()

    provider = _FakeProvider(["215-555-0100"], [])
    await trace_owner(db_session, provider, 1, "000000001")
    again = await trace_owner(db_session, provider, 1, "000000001")
    assert again.credits_spent == 0
    assert again.cached is True
    assert again.credits_remaining == 4
    assert provider.calls == 1


async def test_different_user_burns_on_cache_hit(db_session: AsyncSession) -> None:
    await _add_user(db_session, 1)
    await _add_user(db_session, 2)
    await _add_parcel(db_session, "000000001", owner="JANE DOE")
    await grant_credits(db_session, 1, 5, REASON_PACK_PURCHASE, "pay_1")
    await grant_credits(db_session, 2, 5, REASON_PACK_PURCHASE, "pay_2")
    await db_session.flush()

    provider = _FakeProvider(["215-555-0100"], [])
    await trace_owner(db_session, provider, 1, "000000001")
    other = await trace_owner(db_session, provider, 2, "000000001")
    assert other.credits_spent == 1
    assert other.cached is True
    assert provider.calls == 1


async def test_insufficient_credits_raises(db_session: AsyncSession) -> None:
    await _add_user(db_session, 1)
    await _add_parcel(db_session, "000000001", owner="JANE DOE")
    await db_session.flush()

    provider = _FakeProvider([], [])
    with pytest.raises(QuotaExceededError):
        await trace_owner(db_session, provider, 1, "000000001")


async def test_missing_owner_key_raises(db_session: AsyncSession) -> None:
    await _add_user(db_session, 1)
    await _add_parcel(db_session, "000000001", owner=None)
    await grant_credits(db_session, 1, 5, REASON_INVESTOR_GRANT, "2026-07")
    await db_session.flush()

    provider = _FakeProvider([], [])
    with pytest.raises(ValidationError):
        await trace_owner(db_session, provider, 1, "000000001")


async def test_packet_and_skiptrace_balances_do_not_cross_contaminate(
    db_session: AsyncSession,
) -> None:
    from lotscope.skiptrace.models import REASON_APPEAL_PACKET_GRANT
    from lotscope.skiptrace.service import appeal_packet_balance, spend_appeal_packet_credit

    await _add_user(db_session, 1)
    await grant_credits(db_session, 1, 100, REASON_PACK_PURCHASE, "pay_1")
    await grant_credits(db_session, 1, 1, REASON_APPEAL_PACKET_GRANT, "2026-07")
    await db_session.flush()

    assert await credit_balance(db_session, 1) == 100
    assert await appeal_packet_balance(db_session, 1) == 1

    assert await spend_appeal_packet_credit(db_session, 1, "000000001") is True
    await db_session.flush()

    assert await appeal_packet_balance(db_session, 1) == 0
    assert await credit_balance(db_session, 1) == 100  # skiptrace balance untouched
