from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.accounts.models import User
from lotscope.accounts.security import create_unsubscribe_token
from lotscope.core.config import Settings
from lotscope.core.logging import get_logger
from lotscope.notifications.digest import (
    DealReminderContent,
    DealReminderItem,
    DigestChange,
    DigestContent,
    DigestParcel,
    MatchAlertContent,
    MatchAlertParcel,
    MatchAlertSearch,
    SalesWeekContent,
    SalesWeekItem,
    deal_reminder_subject,
    digest_subject,
    match_alert_subject,
    render_deal_reminder_html,
    render_deal_reminder_text,
    render_digest_html,
    render_digest_text,
    render_match_alert_html,
    render_match_alert_text,
    render_sales_week_html,
    render_sales_week_text,
    sales_week_subject,
)
from lotscope.notifications.email import EmailSender
from lotscope.pipeline.service import deals_due
from lotscope.risk.service import list_sheriff_sales
from lotscope.savedsearch.schemas import SavedSearchAlert
from lotscope.savedsearch.service import (
    alerting_user_ids,
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
        list_unsubscribe=unsubscribe_url,
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
        list_unsubscribe=unsubscribe_url,
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
        list_unsubscribe=unsubscribe_url,
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


_SALES_WEEK_WINDOW = timedelta(days=7)


async def _sales_week_content(session: AsyncSession) -> SalesWeekContent | None:
    today = datetime.now(UTC).date()
    calendar = await list_sheriff_sales(
        session,
        market_code="phl",
        date_from=today,
        date_to=today + _SALES_WEEK_WINDOW,
        limit=50,
    )
    items = [
        SalesWeekItem(
            address=item.address or item.parcel_number,
            sale_date=item.sale_date.isoformat(),
            days_until=(item.sale_date - today).days,
            opening_bid=item.opening_bid,
            opportunity_score=item.opportunity_score,
        )
        for item in calendar.items
        if item.sale_date is not None
    ]
    if not items:
        return None
    return SalesWeekContent(label=calendar.label, items=items)


async def send_sales_week_digest(
    session_factory: async_sessionmaker[AsyncSession],
    sender: EmailSender | None,
    settings: Settings,
) -> int:
    logger = get_logger("notifications")
    if sender is None:
        logger.info("sales_week_skipped_unconfigured")
        return 0

    async with session_factory() as session:
        content = await _sales_week_content(session)
    if content is None:
        logger.info("sales_week_quiet_when_empty")
        return 0

    async with session_factory() as session:
        users = list(
            (
                await session.execute(
                    select(User).where(User.is_active.is_(True), User.digest_frequency != "off")
                )
            )
            .scalars()
            .all()
        )

    calendar_url = f"{settings.app_base_url.rstrip('/')}/philadelphia/sheriff-sales"
    sent = 0
    for user in users:
        token = create_unsubscribe_token(settings, user_id=user.id)
        unsubscribe_url = f"{settings.api_base_url.rstrip('/')}/digests/unsubscribe?token={token}"
        try:
            await sender.send(
                to=user.email,
                subject=sales_week_subject(content),
                html=render_sales_week_html(
                    content,
                    calendar_url=calendar_url,
                    unsubscribe_url=unsubscribe_url,
                    postal_address=settings.company_postal_address,
                ),
                text=render_sales_week_text(
                    content,
                    calendar_url=calendar_url,
                    unsubscribe_url=unsubscribe_url,
                    postal_address=settings.company_postal_address,
                ),
                list_unsubscribe=unsubscribe_url,
            )
            sent += 1
        except Exception:
            logger.exception("sales_week_send_failed", user_id=user.id)

    logger.info("sales_week_sent", count=sent)
    return sent
