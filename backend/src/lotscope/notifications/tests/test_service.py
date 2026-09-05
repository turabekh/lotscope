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

    async def send(
        self,
        *,
        to: str,
        subject: str,
        html: str,
        text: str,
        attachment: object | None = None,
        list_unsubscribe: str | None = None,
    ) -> None:
        self.messages.append(
            {
                "to": to,
                "subject": subject,
                "html": html,
                "text": text,
                "list_unsubscribe": list_unsubscribe or "",
            }
        )


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


async def test_sales_week_content_quiet_when_no_upcoming(db_session: AsyncSession) -> None:
    from lotscope.notifications.service import _sales_week_content

    assert await _sales_week_content(db_session) is None


async def test_sales_week_content_lists_upcoming_phl_sales(db_session: AsyncSession) -> None:
    from lotscope.notifications.service import _sales_week_content

    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, address) VALUES ('phl:000000009', '9 Elm St')")
    )
    await db_session.execute(
        text(
            "INSERT INTO sheriff_sale (parcel_number, case_number, sale_date, status, opening_bid) "
            "VALUES ('phl:000000009', 'BW-9', (now() + interval '3 days')::date, 'Open', 8000)"
        )
    )
    await db_session.flush()

    content = await _sales_week_content(db_session)
    assert content is not None
    assert content.label == "Sheriff sales"
    assert len(content.items) == 1
    assert content.items[0].address == "9 Elm St"
    assert 0 <= content.items[0].days_until <= 7
