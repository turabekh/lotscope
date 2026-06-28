import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.core.config import Settings
from lotscope.notifications.push import PushExpiredError, PushSubscriptionInfo
from lotscope.notifications.service import (
    remove_push_subscription,
    save_push_subscription,
    send_user_push,
)
from lotscope.watchlist.schemas import SavedParcelCreate
from lotscope.watchlist.service import add_saved

pytestmark = pytest.mark.integration


class _FakeSender:
    def __init__(self, *, dead: set[str] | None = None) -> None:
        self.sent: list[str] = []
        self.dead = dead or set()

    async def send(
        self, subscription: PushSubscriptionInfo, *, title: str, body: str, url: str
    ) -> None:
        if subscription.endpoint in self.dead:
            raise PushExpiredError
        self.sent.append(subscription.endpoint)


def _settings() -> Settings:
    return Settings(_env_file=None)


async def _user(session: AsyncSession) -> User:
    await session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
            "VALUES ('p@example.com', 'x', 'user', 'free', true)"
        )
    )
    user_id = await session.scalar(text("SELECT id FROM app_user WHERE email = 'p@example.com'"))
    await session.execute(
        text("INSERT INTO parcel (parcel_number, address) VALUES ('000000001', '1 Main St')")
    )
    await session.flush()
    user = await session.get(User, int(user_id))
    assert user is not None
    return user


async def test_subscribe_upserts_and_unsubscribe(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    await save_push_subscription(
        db_session, user.id, endpoint="https://push/abc", p256dh="k1", auth="a1"
    )
    await save_push_subscription(
        db_session, user.id, endpoint="https://push/abc", p256dh="k2", auth="a2"
    )
    count = await db_session.scalar(
        text("SELECT count(*) FROM push_subscription WHERE user_id = :u"), {"u": user.id}
    )
    keys = await db_session.scalar(
        text("SELECT p256dh FROM push_subscription WHERE endpoint = 'https://push/abc'")
    )
    assert count == 1
    assert keys == "k2"

    await remove_push_subscription(db_session, user.id, "https://push/abc")
    after = await db_session.scalar(
        text("SELECT count(*) FROM push_subscription WHERE user_id = :u"), {"u": user.id}
    )
    assert after == 0


async def test_send_user_push_to_subscriptions(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    await add_saved(db_session, user.id, SavedParcelCreate(parcel_number="000000001"), limit=25)
    await db_session.execute(
        text(
            "INSERT INTO tax_status (parcel_number, is_delinquent, in_sheriff_sale) "
            "VALUES ('000000001', true, true)"
        )
    )
    await save_push_subscription(
        db_session, user.id, endpoint="https://push/live", p256dh="k", auth="a"
    )
    await db_session.flush()

    sender = _FakeSender()
    sent = await send_user_push(db_session, sender, _settings(), user)
    assert sent == 1
    assert sender.sent == ["https://push/live"]


async def test_expired_subscription_is_pruned(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    await add_saved(db_session, user.id, SavedParcelCreate(parcel_number="000000001"), limit=25)
    await db_session.execute(
        text(
            "INSERT INTO tax_status (parcel_number, is_delinquent, in_sheriff_sale) "
            "VALUES ('000000001', true, true)"
        )
    )
    await save_push_subscription(
        db_session, user.id, endpoint="https://push/dead", p256dh="k", auth="a"
    )
    await db_session.flush()

    sender = _FakeSender(dead={"https://push/dead"})
    sent = await send_user_push(db_session, sender, _settings(), user)
    await db_session.flush()
    assert sent == 0
    remaining = await db_session.scalar(text("SELECT count(*) FROM push_subscription"))
    assert remaining == 0


async def test_no_alerts_sends_nothing(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    await add_saved(db_session, user.id, SavedParcelCreate(parcel_number="000000001"), limit=25)
    await save_push_subscription(
        db_session, user.id, endpoint="https://push/x", p256dh="k", auth="a"
    )
    await db_session.flush()

    sender = _FakeSender()
    assert await send_user_push(db_session, sender, _settings(), user) == 0
    assert sender.sent == []
