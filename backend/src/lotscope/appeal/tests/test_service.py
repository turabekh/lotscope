import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.appeal.service import has_entitlement, redeem_packet
from lotscope.core.errors import QuotaExceededError
from lotscope.skiptrace.models import REASON_APPEAL_PACKET_GRANT
from lotscope.skiptrace.service import appeal_packet_balance, grant_credits

pytestmark = pytest.mark.integration


async def _add_user(session: AsyncSession, user_id: int, *, tier: str = "free") -> None:
    await session.execute(
        text(
            "INSERT INTO app_user (id, email, hashed_password, role, tier, is_active) "
            "VALUES (:id, :email, 'x', 'user', :tier, true)"
        ),
        {"id": user_id, "email": f"u{user_id}@example.com", "tier": tier},
    )


async def _add_parcel(session: AsyncSession, parcel_number: str) -> None:
    await session.execute(
        text("INSERT INTO parcel (parcel_number, owner) VALUES (:pn, 'OWNER')"),
        {"pn": parcel_number},
    )


async def test_redeem_without_credit_is_blocked(db_session: AsyncSession) -> None:
    await _add_user(db_session, 1)
    await _add_parcel(db_session, "000000001")
    await db_session.flush()

    with pytest.raises(QuotaExceededError):
        await redeem_packet(db_session, 1, "000000001")
    assert await has_entitlement(db_session, 1, "000000001") is False


async def test_redeem_burns_credit_and_grants_entitlement(db_session: AsyncSession) -> None:
    await _add_user(db_session, 1, tier="investor")
    await _add_parcel(db_session, "000000001")
    await grant_credits(db_session, 1, 1, REASON_APPEAL_PACKET_GRANT, "2026-07")
    await db_session.flush()

    status = await redeem_packet(db_session, 1, "000000001")
    assert status.entitled is True
    assert status.source == "grant"
    assert await appeal_packet_balance(db_session, 1) == 0

    # idempotent: a second redeem does not burn again
    again = await redeem_packet(db_session, 1, "000000001")
    assert again.entitled is True
    assert await appeal_packet_balance(db_session, 1) == 0
