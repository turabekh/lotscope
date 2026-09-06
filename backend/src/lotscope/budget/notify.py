"""The one email that says the Analyst budget is running out."""

from datetime import UTC, datetime
from html import escape
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.core.logging import get_logger
from lotscope.ops.models import OpsAlertState

_logger = get_logger(__name__)


async def admin_emails(session: AsyncSession) -> list[str]:
    return list(
        (
            await session.execute(
                select(User.email)
                .where(User.role == "admin", User.is_active.is_(True))
                .order_by(User.email)
            )
        ).scalars()
    )


def _subject(spend: Any) -> str:
    pct = round(spend.fraction * 100)
    return f"LotScope: Analyst spend is at {pct}% of the daily budget"


def _lines(spend: Any) -> list[str]:
    return [
        f"{row.email}: ${row.total_usd:,.2f} across {row.runs} run(s)" for row in spend.users[:10]
    ]


def render_text(spend: Any, *, analyst_url: str) -> str:
    body = [
        f"Analyst spend for {spend.day.isoformat()} (UTC) is "
        f"${spend.spend_usd:,.2f} of the ${spend.ceiling_usd:,.2f} daily ceiling.",
        "",
        "At the ceiling, new Analyst runs are refused until midnight UTC.",
        "",
        "Today's spend by user:",
        *_lines(spend),
        "",
        analyst_url,
    ]
    return "\n".join(body)


def render_html(spend: Any, *, analyst_url: str) -> str:
    rows = "".join(f"<li>{escape(line)}</li>" for line in _lines(spend))
    return (
        f"<p>Analyst spend for {spend.day.isoformat()} (UTC) is "
        f"<strong>${spend.spend_usd:,.2f}</strong> of the ${spend.ceiling_usd:,.2f} "
        "daily ceiling.</p>"
        "<p>At the ceiling, new Analyst runs are refused until midnight UTC.</p>"
        f"<p>Today's spend by user:</p><ul>{rows}</ul>"
        f'<p><a href="{escape(analyst_url)}">Open the admin spend view</a></p>'
    )


async def _claim_alert_slot(session: AsyncSession, day_start: datetime) -> bool:
    """One email per day. The second run to cross the line must not send a second one."""
    from lotscope.budget.service import GLOBAL_ALERT_KEY

    state = await session.get(OpsAlertState, GLOBAL_ALERT_KEY)
    if state is None:
        session.add(OpsAlertState(key=GLOBAL_ALERT_KEY, last_attempt_at=day_start))
        await session.flush()
        return True
    if state.last_attempt_at is not None and state.last_attempt_at >= day_start:
        return False
    state.last_attempt_at = day_start
    await session.flush()
    return True


async def send_global_budget_alert(
    session: AsyncSession, sender: Any, settings: Any, spend: Any, *, now: datetime | None = None
) -> int:
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    day_start = moment.replace(hour=0, minute=0, second=0, microsecond=0)
    if not await _claim_alert_slot(session, day_start):
        return 0
    recipients = await admin_emails(session)
    if sender is None or not recipients:
        # The slot is still claimed. An unsendable alert must not queue itself up to be
        # sent ten more times the moment SMTP comes back.
        _logger.warning(
            "analyst_budget_alert_not_sent",
            spend_usd=str(spend.spend_usd),
            recipients=len(recipients),
            sender=sender is not None,
        )
        return 0
    analyst_url = f"{settings.app_base_url.rstrip('/')}/admin"
    subject = _subject(spend)
    for email in recipients:
        await sender.send(
            to=email,
            subject=subject,
            html=render_html(spend, analyst_url=analyst_url),
            text=render_text(spend, analyst_url=analyst_url),
        )
    _logger.warning(
        "analyst_budget_alert_sent", spend_usd=str(spend.spend_usd), recipients=len(recipients)
    )
    return len(recipients)
