from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.accounts.schemas import UserCreate
from lotscope.accounts.security import (
    create_calendar_token,
    create_email_verification_token,
    verify_email_verification_token,
)
from lotscope.accounts.service import (
    register_user,
    rotate_verification_nonce,
    verify_email,
)
from lotscope.core.config import get_settings
from lotscope.core.errors import ValidationError

pytestmark = pytest.mark.integration


async def _new_user(session: AsyncSession, email: str) -> User:
    user = await register_user(session, UserCreate(email=email, password="Str0ng!Pass2026"))
    await session.flush()
    return user


def _pending_nonce(user: User) -> str:
    nonce = user.email_verification_nonce
    assert nonce is not None
    return nonce


async def test_a_new_account_starts_unverified_with_a_nonce(db_session: AsyncSession) -> None:
    user = await _new_user(db_session, "start@example.test")

    assert user.email_verified_at is None
    assert user.email_verification_nonce


async def test_the_token_round_trips_and_verifies_once(db_session: AsyncSession) -> None:
    settings = get_settings()
    user = await _new_user(db_session, "once@example.test")
    nonce = _pending_nonce(user)
    token = create_email_verification_token(settings, user_id=user.id, nonce=nonce)

    decoded = verify_email_verification_token(settings, token)
    assert decoded == (user.id, nonce)

    verified = await verify_email(db_session, user.id, decoded[1])
    assert verified.email_verified_at is not None
    assert verified.email_verification_nonce is None

    with pytest.raises(ValidationError):
        await verify_email(db_session, user.id, decoded[1])


async def test_an_expired_token_is_refused() -> None:
    settings = get_settings()
    stale = create_email_verification_token(
        settings,
        user_id=1,
        nonce="whatever",
        now=datetime.now(UTC) - timedelta(hours=25),
    )

    assert verify_email_verification_token(settings, stale) is None


async def test_a_token_signed_for_another_purpose_is_refused() -> None:
    settings = get_settings()
    assert (
        verify_email_verification_token(settings, create_calendar_token(settings, user_id=1))
        is None
    )


async def test_resending_invalidates_the_previous_link(db_session: AsyncSession) -> None:
    settings = get_settings()
    user = await _new_user(db_session, "resend@example.test")
    first = create_email_verification_token(settings, user_id=user.id, nonce=_pending_nonce(user))

    new_nonce = await rotate_verification_nonce(db_session, user)
    stale = verify_email_verification_token(settings, first)
    assert stale is not None

    with pytest.raises(ValidationError):
        await verify_email(db_session, user.id, stale[1])

    verified = await verify_email(db_session, user.id, new_nonce)
    assert verified.email_verified_at is not None


async def test_the_existing_accounts_were_backfilled_as_verified(
    db_session: AsyncSession,
) -> None:
    unverified = await db_session.scalar(
        text("SELECT count(*) FROM app_user WHERE email_verified_at IS NULL")
    )
    assert unverified == 0, (
        "the migration backfills every pre-existing account as verified; leaving them NULL "
        "would lock real users out of the product on deploy"
    )
