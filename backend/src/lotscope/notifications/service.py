from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.accounts.models import User
from lotscope.accounts.security import create_unsubscribe_token
from lotscope.accounts.tiers import feed_access
from lotscope.core.config import Settings
from lotscope.core.logging import get_logger
from lotscope.feed.service import get_feed
from lotscope.notifications.digest import (
    DealReminderContent,
    DealReminderItem,
    DigestChange,
    DigestContent,
    DigestParcel,
    FeedDigestContent,
    FeedDigestLine,
    FeedDigestSearch,
    MatchAlertContent,
    MatchAlertParcel,
    MatchAlertSearch,
    deal_reminder_subject,
    digest_subject,
    feed_digest_subject,
    match_alert_subject,
    render_deal_reminder_html,
    render_deal_reminder_text,
    render_digest_html,
    render_digest_text,
    render_feed_digest_html,
    render_feed_digest_text,
    render_match_alert_html,
    render_match_alert_text,
)
from lotscope.notifications.email import EmailSender
from lotscope.notifications.models import PushSubscription
from lotscope.notifications.push import PushExpiredError, PushSender, PushSubscriptionInfo
from lotscope.pipeline.service import deals_due
from lotscope.savedsearch.schemas import SavedSearchAlert
from lotscope.savedsearch.service import (
    alerting_user_ids,
    list_searches,
    mark_user_notified,
    pending_alerts_for_user,
    run_user_matches,
)
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


def _match_alert_content(alerts: list[SavedSearchAlert]) -> MatchAlertContent:
    return MatchAlertContent(
        searches=[
            MatchAlertSearch(
                name=alert.name,
                parcels=[
                    MatchAlertParcel(
                        parcel_number=match.parcel_number,
                        address=match.address,
                        opportunity_score=match.opportunity_score,
                    )
                    for match in alert.new_matches
                ],
            )
            for alert in alerts
        ]
    )


async def send_user_match_alert(
    session: AsyncSession, sender: EmailSender, settings: Settings, user: User
) -> bool:
    await run_user_matches(session, user.id)
    alerts = await pending_alerts_for_user(session, user.id)
    if not alerts:
        return False
    content = _match_alert_content(alerts)
    token = create_unsubscribe_token(settings, user_id=user.id)
    searches_url = f"{settings.app_base_url.rstrip('/')}/saved-searches"
    unsubscribe_url = f"{settings.api_base_url.rstrip('/')}/digests/unsubscribe?token={token}"
    await sender.send(
        to=user.email,
        subject=match_alert_subject(content),
        html=render_match_alert_html(
            content,
            searches_url=searches_url,
            unsubscribe_url=unsubscribe_url,
            postal_address=settings.company_postal_address,
        ),
        text=render_match_alert_text(
            content,
            searches_url=searches_url,
            unsubscribe_url=unsubscribe_url,
            postal_address=settings.company_postal_address,
        ),
    )
    await mark_user_notified(session, user.id)
    return True


async def send_saved_search_alerts(
    session_factory: async_sessionmaker[AsyncSession],
    sender: EmailSender | None,
    settings: Settings,
) -> int:
    logger = get_logger("notifications")
    if sender is None:
        logger.info("match_alert_skipped_unconfigured")
        return 0

    async with session_factory() as session:
        user_ids = await alerting_user_ids(session)

    sent = 0
    for user_id in user_ids:
        async with session_factory() as session:
            user = await session.get(User, user_id)
            if user is None or not user.is_active:
                continue
            try:
                if await send_user_match_alert(session, sender, settings, user):
                    await session.commit()
                    sent += 1
                else:
                    await session.commit()
            except Exception:
                logger.exception("match_alert_failed", user_id=user_id)

    logger.info("match_alerts_sent", count=sent)
    return sent


_FEED_DIGEST_WINDOW = timedelta(days=1)
_FEED_DIGEST_LIMIT = 5


async def send_user_feed_digest(
    session: AsyncSession, sender: EmailSender, settings: Settings, user: User
) -> bool:
    since = datetime.now(UTC) - _FEED_DIGEST_WINDOW
    searches = [s for s in await list_searches(session, user.id) if s.alerts_enabled]
    digest_searches: list[FeedDigestSearch] = []
    for search in searches:
        result = await get_feed(
            session, criteria=search.criteria, since=since, limit=_FEED_DIGEST_LIMIT
        )
        if result.total == 0:
            continue
        digest_searches.append(
            FeedDigestSearch(
                name=search.name,
                total=result.total,
                lines=[
                    FeedDigestLine(label=item.label, count=item.count) for item in result.summary
                ],
            )
        )
    if not digest_searches:
        return False

    content = FeedDigestContent(searches=digest_searches)
    token = create_unsubscribe_token(settings, user_id=user.id)
    feed_url = f"{settings.app_base_url.rstrip('/')}/philadelphia/feed"
    unsubscribe_url = f"{settings.api_base_url.rstrip('/')}/digests/unsubscribe?token={token}"
    await sender.send(
        to=user.email,
        subject=feed_digest_subject(content),
        html=render_feed_digest_html(
            content,
            feed_url=feed_url,
            unsubscribe_url=unsubscribe_url,
            postal_address=settings.company_postal_address,
        ),
        text=render_feed_digest_text(
            content,
            feed_url=feed_url,
            unsubscribe_url=unsubscribe_url,
            postal_address=settings.company_postal_address,
        ),
    )
    return True


async def send_feed_digests(
    session_factory: async_sessionmaker[AsyncSession],
    sender: EmailSender | None,
    settings: Settings,
) -> int:
    logger = get_logger("notifications")
    if sender is None:
        logger.info("feed_digest_skipped_unconfigured")
        return 0

    async with session_factory() as session:
        user_ids = await alerting_user_ids(session)

    sent = 0
    for user_id in user_ids:
        async with session_factory() as session:
            user = await session.get(User, user_id)
            if user is None or not user.is_active or not feed_access(user.tier):
                continue
            try:
                if await send_user_feed_digest(session, sender, settings, user):
                    sent += 1
            except Exception:
                logger.exception("feed_digest_failed", user_id=user_id)

    logger.info("feed_digests_sent", count=sent)
    return sent


def _due_label(due: date, today: date) -> tuple[str, bool]:
    overdue_days = (today - due).days
    if overdue_days <= 0:
        return "Due today", False
    unit = "day" if overdue_days == 1 else "days"
    return f"{overdue_days} {unit} overdue", True


async def send_user_deal_reminder(
    session: AsyncSession, sender: EmailSender, settings: Settings, user: User
) -> bool:
    today = datetime.now(UTC).date()
    due = await deals_due(session, user.id, today)
    if not due:
        return False
    items: list[DealReminderItem] = []
    for deal in due:
        if deal.next_action_due is None:
            continue
        label, overdue = _due_label(deal.next_action_due, today)
        items.append(
            DealReminderItem(
                address=deal.address or deal.parcel_number,
                stage=deal.stage,
                next_action=deal.next_action,
                due_label=label,
                overdue=overdue,
            )
        )
    if not items:
        return False
    content = DealReminderContent(items=items)
    token = create_unsubscribe_token(settings, user_id=user.id)
    pipeline_url = f"{settings.app_base_url.rstrip('/')}/philadelphia/pipeline"
    unsubscribe_url = f"{settings.api_base_url.rstrip('/')}/digests/unsubscribe?token={token}"
    await sender.send(
        to=user.email,
        subject=deal_reminder_subject(content),
        html=render_deal_reminder_html(
            content,
            pipeline_url=pipeline_url,
            unsubscribe_url=unsubscribe_url,
            postal_address=settings.company_postal_address,
        ),
        text=render_deal_reminder_text(
            content,
            pipeline_url=pipeline_url,
            unsubscribe_url=unsubscribe_url,
            postal_address=settings.company_postal_address,
        ),
    )
    return True


async def send_deal_reminders(
    session_factory: async_sessionmaker[AsyncSession],
    sender: EmailSender | None,
    settings: Settings,
) -> int:
    logger = get_logger("notifications")
    if sender is None:
        logger.info("deal_reminders_skipped_unconfigured")
        return 0

    async with session_factory() as session:
        user_ids = list(
            (
                await session.execute(
                    select(User.id).where(User.is_active.is_(True), User.digest_frequency != "off")
                )
            ).scalars()
        )

    sent = 0
    for user_id in user_ids:
        async with session_factory() as session:
            user = await session.get(User, user_id)
            if user is None or not user.is_active:
                continue
            try:
                if await send_user_deal_reminder(session, sender, settings, user):
                    sent += 1
            except Exception:
                logger.exception("deal_reminder_failed", user_id=user_id)

    logger.info("deal_reminders_sent", count=sent)
    return sent
