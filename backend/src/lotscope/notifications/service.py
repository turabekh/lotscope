from sqlalchemy import select
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
