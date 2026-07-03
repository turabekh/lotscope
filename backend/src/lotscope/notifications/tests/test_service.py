import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.core.config import Settings
from lotscope.notifications.service import send_user_digest
from lotscope.watchlist.schemas import SavedParcelCreate
from lotscope.watchlist.service import add_saved, list_saved

pytestmark = pytest.mark.integration


class _FakeSender:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    async def send(self, *, to: str, subject: str, html: str, text: str) -> None:
        self.messages.append({"to": to, "subject": subject, "html": html, "text": text})


def _settings() -> Settings:
    return Settings(_env_file=None, secret_key="test-secret-key-test-secret-key-32")


async def _user(session: AsyncSession) -> User:
    await session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active, digest_frequency)"
            " VALUES ('w@example.com', 'x', 'user', 'free', true, 'weekly')"
        )
    )
    user = await session.scalar(text("SELECT id FROM app_user WHERE email = 'w@example.com'"))
    assert user is not None
    await session.execute(
        text("INSERT INTO parcel (parcel_number, address) VALUES ('000000001', '1 Main St')")
    )
    await session.flush()
    return await session.get(User, int(user))  # type: ignore[return-value]


async def test_send_user_digest_emails_alerts_then_clears(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    await add_saved(db_session, user.id, SavedParcelCreate(parcel_number="000000001"), limit=25)
    # parcel becomes distressed after it was saved
    await db_session.execute(
        text(
            "INSERT INTO tax_status (parcel_number, is_delinquent, total_due, in_sheriff_sale) "
            "VALUES ('000000001', true, 12000, true)"
        )
    )
    await db_session.flush()

    sender = _FakeSender()
    sent = await send_user_digest(db_session, sender, _settings(), user)

    assert sent is True
    assert len(sender.messages) == 1
    message = sender.messages[0]
    assert message["to"] == "w@example.com"
    assert "1 Main St" in message["html"]
    assert "sheriff sale" in message["html"].lower()
    assert "unsubscribe?token=" in message["html"]

    # sending acknowledged the alerts, so the next pass has nothing to send
    assert all(not item.has_alerts for item in await list_saved(db_session, user.id))
    assert await send_user_digest(db_session, sender, _settings(), user) is False


async def test_send_user_digest_no_alerts_is_noop(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    await add_saved(db_session, user.id, SavedParcelCreate(parcel_number="000000001"), limit=25)

    sender = _FakeSender()
    assert await send_user_digest(db_session, sender, _settings(), user) is False
    assert sender.messages == []


async def test_send_user_feed_digest_emails_investor_with_events(db_session: AsyncSession) -> None:
    from lotscope.notifications.service import send_user_feed_digest
    from lotscope.savedsearch.schemas import SavedSearchCreate, SearchCriteria
    from lotscope.savedsearch.service import create_search

    await db_session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
            "VALUES ('inv@example.com', 'x', 'user', 'investor', true)"
        )
    )
    uid = await db_session.scalar(text("SELECT id FROM app_user WHERE email = 'inv@example.com'"))
    assert uid is not None
    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, owner, is_vacant) VALUES ('000000001', 'O', true)")
    )
    await db_session.execute(
        text(
            "INSERT INTO parcel_event (parcel_number, dataset, code, severity) "
            "VALUES ('000000001', 'tax_delinquency', 'delinquent', 'high')"
        )
    )
    await create_search(
        db_session,
        int(uid),
        SavedSearchCreate(name="My buy box", criteria=SearchCriteria(), alerts_enabled=True),
        limit=None,
    )
    await db_session.flush()

    user = await db_session.get(User, int(uid))
    assert user is not None
    sender = _FakeSender()
    sent = await send_user_feed_digest(db_session, sender, _settings(), user)

    assert sent is True
    assert len(sender.messages) == 1
    assert "buy box" in sender.messages[0]["subject"]
    assert "delinquenc" in sender.messages[0]["html"].lower()


async def test_send_user_feed_digest_noop_without_events(db_session: AsyncSession) -> None:
    from lotscope.notifications.service import send_user_feed_digest
    from lotscope.savedsearch.schemas import SavedSearchCreate, SearchCriteria
    from lotscope.savedsearch.service import create_search

    await db_session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
            "VALUES ('inv2@example.com', 'x', 'user', 'investor', true)"
        )
    )
    uid = await db_session.scalar(text("SELECT id FROM app_user WHERE email = 'inv2@example.com'"))
    assert uid is not None
    await create_search(
        db_session,
        int(uid),
        SavedSearchCreate(name="Quiet box", criteria=SearchCriteria(), alerts_enabled=True),
        limit=None,
    )
    await db_session.flush()

    user = await db_session.get(User, int(uid))
    assert user is not None
    sender = _FakeSender()
    assert await send_user_feed_digest(db_session, sender, _settings(), user) is False
    assert sender.messages == []
