"""The morning brief: what changed overnight, in eight lines or fewer.

The Analyst writes it from the signals built after the ingest, and only from those. It runs
in brief mode with no tools registered — not as a restriction on what it may say, but because
a brief that goes looking for extra facts is a brief with lines no signal stands behind.
"""

import json
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.accounts.models import User
from lotscope.accounts.security import create_unsubscribe_token
from lotscope.agent.runtime import ModelClient, create_run, ensure_conversation, run_agent
from lotscope.agent.signals import AnalystBrief, AnalystSignal
from lotscope.agent.tools.registry import ToolContext, ToolRegistry
from lotscope.budget.service import JOB_SOURCE, check_analyst_budget, record_analyst_usage
from lotscope.buybox.models import BuyBox
from lotscope.buybox.service import read_buy_box
from lotscope.core.config import Settings
from lotscope.core.logging import get_logger
from lotscope.notifications.digest import (
    BriefContent,
    brief_subject,
    render_brief_html,
    render_brief_text,
)
from lotscope.notifications.email import EmailSender

MAX_BRIEF_ITEMS = 8
BRIEF_MAX_OUTPUT_TOKENS = 1200
NOTHING_CHANGED = "Nothing changed overnight on anything you are watching."

_logger = get_logger(__name__)

# Deliberately empty: in brief mode the signals are the whole input.
NO_TOOLS = ToolRegistry()


async def _packet_today(
    session: AsyncSession, user_id: int, on_date: date
) -> dict[str, Any] | None:
    row = (
        (
            await session.execute(
                text(
                    "SELECT id, sale_date, status FROM sale_packet "
                    "WHERE user_id = :u AND sale_date = :d ORDER BY id DESC LIMIT 1"
                ),
                {"u": user_id, "d": on_date},
            )
        )
        .mappings()
        .one_or_none()
    )
    return dict(row) if row else None


def brief_question(
    signals: list[AnalystSignal], packet: dict[str, Any] | None, app_base_url: str
) -> str:
    lines = [
        f"Today is {datetime.now(UTC).date().isoformat()}. "
        f"Here are the {len(signals)} signals found overnight."
    ]
    for signal in signals:
        lines.append(
            json.dumps(
                {
                    "kind": signal.kind,
                    "headline": signal.headline,
                    "parcel": signal.parcel_number,
                    "detail": signal.detail,
                    "source": signal.source,
                    "source_url": signal.source_url,
                    "from_row": f"{signal.source_table}#{signal.source_row_id}",
                    "observed_at": signal.observed_at.isoformat() if signal.observed_at else None,
                },
                default=str,
            )
        )
    if packet is not None:
        lines.append(
            f"A sale packet for {packet['sale_date']} is scheduled to reach them at 09:00 "
            f"today ({app_base_url.rstrip('/')}/packets). One line pointing at it; do not "
            f"restate its contents."
        )
    return "\n".join(lines)


async def _write_brief(
    session: AsyncSession,
    client: ModelClient,
    settings: Settings,
    *,
    user_id: int,
    signals: list[AnalystSignal],
    on_date: date,
) -> tuple[str, int | None, int, int]:
    buy_box = await read_buy_box(session, user_id)
    packet = await _packet_today(session, user_id, on_date)
    question = brief_question(signals, packet, settings.app_base_url)

    conversation = await ensure_conversation(session, user_id, None, f"brief {on_date.isoformat()}")
    run = await create_run(
        session,
        user_id=user_id,
        conversation=conversation,
        question=question,
        model=settings.analyst_model,
    )
    await session.flush()

    context = ToolContext(
        user_id=user_id,
        buy_box=buy_box.model_dump(mode="json"),
        owned_parcels=tuple(buy_box.owned_parcels),
    )
    parts: list[str] = []
    async for event in run_agent(
        session, client, run, context=context, registry=NO_TOOLS, mode="brief"
    ):
        if event.kind == "text_delta":
            parts.append(event.payload["text"])

    # Recorded under `job`, not `chat`: this is real spend on the invoice and the global
    # ceiling counts it, but a brief the buyer did not ask for must never be the reason
    # their next question is refused.
    await record_analyst_usage(
        session,
        user_id=user_id,
        model=run.model,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        source=JOB_SOURCE,
    )
    return "".join(parts).strip(), run.id, run.input_tokens, run.output_tokens


async def generate_brief(
    session: AsyncSession,
    client: ModelClient,
    settings: Settings,
    *,
    user_id: int,
    on_date: date,
    signals: list[AnalystSignal] | None = None,
) -> AnalystBrief | None:
    """Write and store one brief. Returns None when there was nothing to say."""
    if signals is None:
        signals = list(
            (
                await session.execute(
                    select(AnalystSignal)
                    .where(AnalystSignal.user_id == user_id, AnalystSignal.signal_date == on_date)
                    .order_by(AnalystSignal.id)
                )
            )
            .scalars()
            .all()
        )

    existing = (
        await session.execute(
            select(AnalystBrief).where(
                AnalystBrief.user_id == user_id, AnalystBrief.brief_date == on_date
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    if not signals:
        # No signals, no model call, no email. A daily "nothing happened" mail is how a
        # useful alert becomes one people filter away.
        _logger.info("brief_skipped_no_signals", user_id=user_id, date=on_date.isoformat())
        return None

    # The buyer's own ceiling does not apply to the brief, but the platform's does. If
    # the day's model budget is gone, the nightly job is exactly the spend to stop.
    user = await session.get(User, user_id)
    if user is not None:
        verdict = await check_analyst_budget(session, user, settings, source=JOB_SOURCE)
        if not verdict.allowed:
            _logger.warning(
                "brief_skipped_over_budget", user_id=user_id, reason=verdict.reason
            )
            return None

    text_body, run_id, _, _ = await _write_brief(
        session, client, settings, user_id=user_id, signals=signals, on_date=on_date
    )
    if not text_body:
        _logger.warning("brief_empty", user_id=user_id, date=on_date.isoformat())
        return None

    brief = AnalystBrief(
        user_id=user_id,
        brief_date=on_date,
        text=text_body,
        signal_count=len(signals),
        run_id=run_id,
    )
    session.add(brief)
    await session.flush()
    return brief


async def _send(sender: EmailSender, settings: Settings, user: User, brief: AnalystBrief) -> None:
    content = BriefContent(
        brief_date=brief.brief_date,
        body=brief.text,
        signal_count=brief.signal_count,
        analyst_url=f"{settings.app_base_url.rstrip('/')}/analyst",
    )
    token = create_unsubscribe_token(settings, user_id=user.id)
    unsubscribe_url = f"{settings.api_base_url.rstrip('/')}/digests/unsubscribe?token={token}"
    await sender.send(
        to=user.email,
        subject=brief_subject(content),
        html=render_brief_html(content, unsubscribe_url),
        text=render_brief_text(content, unsubscribe_url),
        list_unsubscribe=f"<{unsubscribe_url}>",
    )


async def send_daily_briefs(
    factory: async_sessionmaker[AsyncSession],
    client: ModelClient,
    sender: EmailSender | None,
    settings: Settings,
    *,
    on_date: date | None = None,
) -> int:
    on_date = on_date or datetime.now(UTC).date()
    async with factory() as session:
        users = list(
            (
                await session.execute(
                    select(User)
                    .join(BuyBox, BuyBox.user_id == User.id)
                    .where(User.is_active.is_(True), User.email_verified_at.is_not(None))
                    .order_by(User.id)
                )
            )
            .scalars()
            .all()
        )

    sent = 0
    for user in users:
        async with factory() as session:
            try:
                brief = await generate_brief(
                    session, client, settings, user_id=user.id, on_date=on_date
                )
            except Exception as cause:
                await session.rollback()
                _logger.error("brief_failed", user_id=user.id, error=str(cause))
                continue
            if brief is None:
                await session.commit()
                continue
            if brief.emailed_at is not None:
                await session.commit()
                continue
            if sender is None:
                # No SMTP configured. The brief is still written and readable at /briefs;
                # marking it emailed would be a lie the next run could not undo.
                await session.commit()
                _logger.info("brief_written_not_emailed", user_id=user.id)
                continue
            try:
                await _send(sender, settings, user, brief)
            except Exception as cause:
                # The brief is written and stored; only the delivery failed. Committing it
                # without emailed_at means tomorrow's run will not rewrite it, and the
                # failure is visible rather than swallowed behind a success count.
                await session.commit()
                _logger.error("brief_email_failed", user_id=user.id, error=str(cause))
                continue
            brief.emailed_at = datetime.now(UTC)
            await session.commit()
            sent += 1
    return sent


async def build_and_brief(
    factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    *,
    on_date: date | None = None,
    since: datetime | None = None,
) -> int:
    """Build every active buyer's signals for the day. Returns how many rows were written."""
    from lotscope.agent.signal_builder import build_signals

    on_date = on_date or datetime.now(UTC).date()
    since = since or (datetime.now(UTC) - timedelta(hours=26))

    async with factory() as session:
        user_ids = list(
            (
                await session.execute(
                    select(User.id)
                    .join(BuyBox, BuyBox.user_id == User.id)
                    .where(User.is_active.is_(True))
                    .order_by(User.id)
                )
            )
            .scalars()
            .all()
        )

    built = 0
    for user_id in user_ids:
        async with factory() as session:
            try:
                buy_box = await read_buy_box(session, user_id)
                signals = await build_signals(
                    session, user_id=user_id, buy_box=buy_box, on_date=on_date, since=since
                )
                await session.commit()
            except Exception as cause:
                await session.rollback()
                _logger.error("signal_build_failed", user_id=user_id, error=str(cause))
                continue
        built += len(signals)
        _logger.info("signals_built", user_id=user_id, count=len(signals))
    return built
