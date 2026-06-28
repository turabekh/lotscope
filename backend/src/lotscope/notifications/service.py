from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.accounts.models import User
from lotscope.accounts.security import create_unsubscribe_token
from lotscope.core.config import Settings
from lotscope.core.logging import get_logger
from lotscope.notifications.digest import (
    DigestChange,
    DigestContent,
    DigestParcel,
    digest_subject,
    render_digest_html,
    render_digest_text,
)
from lotscope.notifications.email import EmailSender
from lotscope.notifications.models import PushSubscription
from lotscope.notifications.push import PushExpiredError, PushSender, PushSubscriptionInfo
from lotscope.watchlist.schemas import WatchlistItem
from lotscope.watchlist.service import acknowledge, list_saved


def _digest_content(items: list[WatchlistItem]) -> DigestContent:
    return DigestContent(
        parcels=[
            DigestParcel(
                parcel_number=item.parcel_number,
                address=item.address,
                changes=[DigestChange(label=c.label, severity=c.severity) for c in item.changes],
            )
            for item in items
        ]
    )


async def send_user_digest(
    session: AsyncSession, sender: EmailSender, settings: Settings, user: User
) -> bool:
    alerted = [item for item in await list_saved(session, user.id) if item.has_alerts]
    if not alerted:
        return False
    content = _digest_content(alerted)
    token = create_unsubscribe_token(settings, user_id=user.id)
    watchlist_url = f"{settings.app_base_url.rstrip('/')}/watchlist"
    unsubscribe_url = f"{settings.api_base_url.rstrip('/')}/digests/unsubscribe?token={token}"
    await sender.send(
        to=user.email,
        subject=digest_subject(content),
        html=render_digest_html(
            content,
            watchlist_url=watchlist_url,
            unsubscribe_url=unsubscribe_url,
            postal_address=settings.company_postal_address,
        ),
        text=render_digest_text(
            content,
            watchlist_url=watchlist_url,
            unsubscribe_url=unsubscribe_url,
            postal_address=settings.company_postal_address,
        ),
    )
    for item in alerted:
        await acknowledge(session, user.id, item.parcel_number)
    return True


async def send_digests(
    session_factory: async_sessionmaker[AsyncSession],
    sender: EmailSender | None,
    settings: Settings,
    *,
    frequency: str,
) -> int:
    logger = get_logger("notifications")
    if sender is None:
        logger.info("digest_skipped_unconfigured", frequency=frequency)
        return 0

    async with session_factory() as session:
        users = list(
            (
                await session.execute(
                    select(User).where(User.digest_frequency == frequency, User.is_active.is_(True))
                )
            )
            .scalars()
            .all()
        )

    sent = 0
    for user in users:
        async with session_factory() as session:
            try:
                if await send_user_digest(session, sender, settings, user):
                    await session.commit()
                    sent += 1
            except Exception:
                logger.exception("digest_send_failed", user_id=user.id)

    logger.info("digests_sent", frequency=frequency, count=sent)
    return sent


async def save_push_subscription(
    session: AsyncSession, user_id: int, *, endpoint: str, p256dh: str, auth: str
) -> None:
    statement = insert(PushSubscription).values(
        user_id=user_id, endpoint=endpoint, p256dh=p256dh, auth=auth
    )
    statement = statement.on_conflict_do_update(
        index_elements=["endpoint"],
        set_={"user_id": user_id, "p256dh": p256dh, "auth": auth},
    )
    await session.execute(statement)


async def remove_push_subscription(session: AsyncSession, user_id: int, endpoint: str) -> None:
    await session.execute(
        delete(PushSubscription).where(
            PushSubscription.user_id == user_id, PushSubscription.endpoint == endpoint
        )
    )


async def send_user_push(
    session: AsyncSession, sender: PushSender, settings: Settings, user: User
) -> int:
    alerted = [item for item in await list_saved(session, user.id) if item.has_alerts]
    if not alerted:
        return 0
    subscriptions = list(
        (await session.execute(select(PushSubscription).where(PushSubscription.user_id == user.id)))
        .scalars()
        .all()
    )
    if not subscriptions:
        return 0
    lots = len(alerted)
    title = "LotScope — watchlist updates"
    body = f"{lots} watched lot{'' if lots == 1 else 's'} changed. Open to review."
    url = f"{settings.app_base_url.rstrip('/')}/watchlist"
    sent = 0
    for subscription in subscriptions:
        info = PushSubscriptionInfo(
            endpoint=subscription.endpoint, p256dh=subscription.p256dh, auth=subscription.auth
        )
        try:
            await sender.send(info, title=title, body=body, url=url)
            sent += 1
        except PushExpiredError:
            await session.delete(subscription)
    return sent


async def send_push_alerts(
    session_factory: async_sessionmaker[AsyncSession],
    sender: PushSender | None,
    settings: Settings,
) -> int:
    logger = get_logger("notifications")
    if sender is None:
        logger.info("push_skipped_unconfigured")
        return 0
    async with session_factory() as session:
        user_ids = list(
            (await session.execute(select(PushSubscription.user_id).distinct())).scalars().all()
        )

    sent = 0
    for user_id in user_ids:
        async with session_factory() as session:
            user = await session.get(User, user_id)
            if user is None or not user.is_active:
                continue
            try:
                sent += await send_user_push(session, sender, settings, user)
                await session.commit()
            except Exception:
                logger.exception("push_send_failed", user_id=user_id)

    logger.info("push_alerts_sent", count=sent)
    return sent
