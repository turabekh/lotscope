from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.core.config import Settings
from lotscope.notifications.service import send_user_deal_reminder
from lotscope.pipeline.schemas import DealCreate, DealUpdate
from lotscope.pipeline.service import add_deal, update_deal

pytestmark = pytest.mark.integration

_TODAY = datetime.now(UTC).date()


class _FakeSender:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    async def send(
        self, *, to: str, subject: str, html: str, text: str, attachment: object = None
    ) -> None:
        self.messages.append({"to": to, "subject": subject, "html": html, "text": text})


def _settings() -> Settings:
    return Settings(_env_file=None, secret_key="test-secret-key-test-secret-key-32")


async def _user(session: AsyncSession) -> User:
    await session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
            "VALUES ('deals@example.com', 'x', 'user', 'pro', true)"
        )
    )
    await session.execute(
        text("INSERT INTO parcel (parcel_number, address) VALUES ('000000001', '1 Main St')")
    )
    await session.flush()
    user = await session.scalar(text("SELECT id FROM app_user WHERE email = 'deals@example.com'"))
    fetched = await session.get(User, int(user))
    assert fetched is not None
    return fetched


async def test_reminder_lists_overdue_deal(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    await add_deal(db_session, user.id, DealCreate(parcel_number="000000001"), limit=None)
    await update_deal(
        db_session,
        user.id,
        "000000001",
        DealUpdate(next_action="Call owner", next_action_due=_TODAY - timedelta(days=3)),
    )

    sender = _FakeSender()
    sent = await send_user_deal_reminder(db_session, sender, _settings(), user)
    assert sent is True
    assert sender.messages[0]["to"] == "deals@example.com"
    assert "overdue" in sender.messages[0]["subject"].lower()
    assert "Call owner" in sender.messages[0]["text"]


async def test_reminder_is_quiet_without_due_deals(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    await add_deal(db_session, user.id, DealCreate(parcel_number="000000001"), limit=None)

    sender = _FakeSender()
    sent = await send_user_deal_reminder(db_session, sender, _settings(), user)
    assert sent is False
    assert sender.messages == []
