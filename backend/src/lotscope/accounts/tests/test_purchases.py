from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import BuyerInvite, User
from lotscope.accounts.purchases import (
    INVITE_COMP_DAYS,
    PACKET_SKU,
    SKU_PRICES_CENTS,
    has_paid,
    is_comped,
    mark_paid,
    may_download,
    record_session,
    redeem_invite,
)

pytestmark = pytest.mark.integration

NOW = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)


async def _user(session: AsyncSession, email: str) -> User:
    await session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
            "VALUES (:e, 'x', 'user', 'user', true)"
        ),
        {"e": email},
    )
    await session.flush()
    user_id = int(
        await session.scalar(text("SELECT id FROM app_user WHERE email=:e"), {"e": email})
    )
    found = await session.get(User, user_id)
    assert found is not None
    return found


async def test_the_webhook_is_idempotent_on_the_session_id(db_session: AsyncSession) -> None:
    user = await _user(db_session, "idem@example.com")
    await record_session(
        db_session, user_id=user.id, sku=PACKET_SKU, object_ref="7", stripe_session_id="cs_1"
    )

    first = await mark_paid(db_session, "cs_1", now=NOW)
    second = await mark_paid(db_session, "cs_1", now=NOW + timedelta(hours=3))

    assert first is not None
    assert second is not None
    assert first.id == second.id
    assert first.paid_at == NOW
    assert second.paid_at == NOW
    rows = await db_session.scalar(text("SELECT count(*) FROM purchase"))
    assert rows == 1


async def test_recording_the_same_session_twice_creates_one_purchase(
    db_session: AsyncSession,
) -> None:
    user = await _user(db_session, "once@example.com")

    a = await record_session(
        db_session, user_id=user.id, sku=PACKET_SKU, object_ref="7", stripe_session_id="cs_2"
    )
    b = await record_session(
        db_session, user_id=user.id, sku=PACKET_SKU, object_ref="7", stripe_session_id="cs_2"
    )

    assert a.id == b.id
    assert a.amount_cents == SKU_PRICES_CENTS[PACKET_SKU] == 4900


async def test_an_unknown_session_id_marks_nothing(db_session: AsyncSession) -> None:
    assert await mark_paid(db_session, "cs_never_seen") is None


async def test_the_download_gate_opens_only_once_paid(db_session: AsyncSession) -> None:
    user = await _user(db_session, "gate@example.com")
    await record_session(
        db_session, user_id=user.id, sku=PACKET_SKU, object_ref="7", stripe_session_id="cs_3"
    )

    assert await may_download(db_session, user, PACKET_SKU, "7") is False
    await mark_paid(db_session, "cs_3", now=NOW)
    assert await may_download(db_session, user, PACKET_SKU, "7") is True
    assert await has_paid(db_session, user.id, PACKET_SKU, "7") is True


async def test_paying_for_one_packet_does_not_open_another(db_session: AsyncSession) -> None:
    user = await _user(db_session, "scoped@example.com")
    await record_session(
        db_session, user_id=user.id, sku=PACKET_SKU, object_ref="7", stripe_session_id="cs_4"
    )
    await mark_paid(db_session, "cs_4", now=NOW)

    assert await may_download(db_session, user, PACKET_SKU, "7") is True
    assert await may_download(db_session, user, PACKET_SKU, "8") is False


async def test_a_comp_opens_the_gate_and_an_expired_one_closes_it(
    db_session: AsyncSession,
) -> None:
    user = await _user(db_session, "comped@example.com")

    user.comp_until = NOW + timedelta(days=1)
    assert is_comped(user, now=NOW) is True
    assert await may_download(db_session, user, PACKET_SKU, "7", now=NOW) is True

    user.comp_until = NOW - timedelta(days=1)
    assert is_comped(user, now=NOW) is False
    assert await may_download(db_session, user, PACKET_SKU, "7", now=NOW) is False


async def test_no_comp_at_all_is_not_comped(db_session: AsyncSession) -> None:
    user = await _user(db_session, "nocomp@example.com")

    assert user.comp_until is None
    assert is_comped(user, now=NOW) is False


async def test_an_invite_code_grants_a_comp_and_records_the_redemption(
    db_session: AsyncSession,
) -> None:
    user = await _user(db_session, "invited@example.com")
    db_session.add(BuyerInvite(buyer_key="ACME LLC", code="JK4W4ZKZ", display_name="Acme LLC"))
    await db_session.flush()

    granted = await redeem_invite(db_session, user, token_key=None, code="jk4w4zkz")

    assert granted is True
    assert user.comp_until is not None
    assert user.comp_until > datetime.now(UTC) + timedelta(days=INVITE_COMP_DAYS - 1)
    invite = await db_session.get(BuyerInvite, "ACME LLC")
    assert invite is not None
    assert invite.redeemed_by_user_id == user.id
    assert invite.redeemed_at is not None


async def test_an_invite_token_grants_a_comp_by_buyer_key(db_session: AsyncSession) -> None:
    user = await _user(db_session, "token@example.com")
    db_session.add(
        BuyerInvite(buyer_key="BRONZE CAPITAL LLC", code="AAAA1111", display_name="Bronze")
    )
    await db_session.flush()

    granted = await redeem_invite(db_session, user, token_key="BRONZE CAPITAL LLC", code=None)

    assert granted is True
    assert user.comp_until is not None


async def test_an_unknown_invite_grants_nothing(db_session: AsyncSession) -> None:
    user = await _user(db_session, "stranger@example.com")

    assert await redeem_invite(db_session, user, token_key=None, code="NOTREAL1") is False
    assert user.comp_until is None
