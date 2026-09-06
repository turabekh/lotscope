"""What the Analyst is allowed to spend, per buyer and in total.

Two ceilings, because they protect different things. The per-user ceiling stops one
buyer's afternoon from consuming the month's model budget; the global ceiling stops
every buyer together from doing it, and it is the last line before the invoice.

Both are read before a run starts and again inside it. A single question can call
twenty-five tools and run for a minute, so a ceiling that is only checked at the door
is a ceiling a long run walks straight through.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.budget.models import AnalystUsage
from lotscope.budget.pricing import usd_estimate
from lotscope.core.config import Settings

Source = Literal["chat", "job"]

CHAT_SOURCE: Source = "chat"
JOB_SOURCE: Source = "job"

GLOBAL_ALERT_KEY = "analyst_global_budget"


@dataclass(frozen=True)
class BudgetVerdict:
    """Whether the next run may start, and what to tell the buyer if it may not."""

    allowed: bool
    reason: str | None = None
    message: str = ""

    def __bool__(self) -> bool:
        return self.allowed


ALLOWED = BudgetVerdict(allowed=True)


@dataclass(frozen=True)
class UserSpend:
    user_id: int
    email: str
    chat_usd: Decimal
    job_usd: Decimal
    total_usd: Decimal
    runs: int
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class GlobalSpend:
    day: date
    spend_usd: Decimal
    ceiling_usd: Decimal
    users: list[UserSpend]

    @property
    def fraction(self) -> float:
        if self.ceiling_usd <= 0:
            return 1.0
        return float(self.spend_usd / self.ceiling_usd)


def today(now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).astimezone(UTC).date()


def user_ceilings(user: User, settings: Settings) -> tuple[Decimal, int]:
    """The buyer's own ceiling if an admin set one, otherwise the platform default.

    A comped account gets the same ceiling as a paying one. Comp waives the price of a
    document, not the cost of the model, and the one account most likely to be handed
    out freely is the one most in need of a ceiling.
    """
    usd = user.analyst_daily_usd
    runs = user.analyst_daily_runs
    return (
        Decimal(str(settings.analyst_daily_usd_per_user)) if usd is None else Decimal(usd),
        int(settings.analyst_daily_runs_per_user) if runs is None else int(runs),
    )


def _money(value: Decimal) -> str:
    return f"${value:,.2f}"


def over_user_usd(spent: Decimal, ceiling: Decimal) -> str:
    return (
        f"You have used {_money(spent)} of your {_money(ceiling)} daily Analyst budget, so "
        "this run stopped here. The budget resets at midnight UTC. Ask an admin to raise "
        "your ceiling if you need more today."
    )


def over_user_runs(runs: int, ceiling: int) -> str:
    return (
        f"You have run the Analyst {runs} times today, which is your daily limit of "
        f"{ceiling}. The limit resets at midnight UTC. Ask an admin to raise your ceiling "
        "if you need more today."
    )


def over_global(spent: Decimal, ceiling: Decimal) -> str:
    return (
        f"LotScope has reached its {_money(ceiling)} daily Analyst budget "
        f"({_money(spent)} spent), so no new runs can start until midnight UTC. This is a "
        "platform limit, not something about your account. The team has been emailed."
    )


async def _row(
    session: AsyncSession, user_id: int, day: date, source: Source
) -> AnalystUsage | None:
    return (
        await session.execute(
            select(AnalystUsage).where(
                AnalystUsage.user_id == user_id,
                AnalystUsage.day == day,
                AnalystUsage.source == source,
            )
        )
    ).scalar_one_or_none()


async def chat_spend(session: AsyncSession, user_id: int, day: date) -> tuple[Decimal, int]:
    row = await _row(session, user_id, day, CHAT_SOURCE)
    if row is None:
        return Decimal(0), 0
    return Decimal(row.usd_estimate), int(row.runs)


async def global_spend(session: AsyncSession, day: date) -> Decimal:
    """Every source, because the invoice does not care which job spent it."""
    value = await session.scalar(
        text("SELECT coalesce(sum(usd_estimate), 0) FROM analyst_usage WHERE day = :d"),
        {"d": day},
    )
    return Decimal(str(value or 0))


async def check_analyst_budget(
    session: AsyncSession,
    user: User,
    settings: Settings,
    *,
    source: Source = CHAT_SOURCE,
    pending_input_tokens: int = 0,
    pending_output_tokens: int = 0,
    model: str | None = None,
    now: datetime | None = None,
) -> BudgetVerdict:
    """Read both ceilings, counting what this run has already spent but not yet recorded.

    The pending figures are what makes the mid-run check work: a run's tokens land in
    `analyst_usage` only when it ends, so during the run the only record of its spend is
    the counter the runtime is holding.
    """
    day = today(now)
    pending_usd = (
        usd_estimate(model or settings.analyst_model, pending_input_tokens, pending_output_tokens)
        if pending_input_tokens or pending_output_tokens
        else Decimal(0)
    )

    global_ceiling = Decimal(str(settings.analyst_daily_usd_global))
    spent_globally = await global_spend(session, day) + pending_usd
    if spent_globally >= global_ceiling:
        return BudgetVerdict(False, "global_usd", over_global(spent_globally, global_ceiling))

    # The nightly brief is exempt from the buyer's own ceiling: it is spend the buyer did
    # not ask for at that moment, and it must never be why their next question is refused.
    if source != CHAT_SOURCE:
        return ALLOWED

    usd_ceiling, run_ceiling = user_ceilings(user, settings)
    spent, runs = await chat_spend(session, user.id, day)
    spent += pending_usd
    if spent >= usd_ceiling:
        return BudgetVerdict(False, "user_usd", over_user_usd(spent, usd_ceiling))
    if runs >= run_ceiling:
        return BudgetVerdict(False, "user_runs", over_user_runs(runs, run_ceiling))
    return ALLOWED


async def record_analyst_usage(
    session: AsyncSession,
    *,
    user_id: int,
    model: str,
    input_tokens: int,
    output_tokens: int,
    source: Source = CHAT_SOURCE,
    runs: int = 1,
    now: datetime | None = None,
) -> Decimal:
    """Add one run to the day's ledger. Returns what that run cost."""
    cost = usd_estimate(model, input_tokens, output_tokens)
    day = today(now)
    statement = insert(AnalystUsage).values(
        user_id=user_id,
        day=day,
        source=source,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        usd_estimate=cost,
        runs=runs,
    )
    await session.execute(
        statement.on_conflict_do_update(
            constraint="uq_analyst_usage_user_day_source",
            set_={
                "input_tokens": AnalystUsage.input_tokens + statement.excluded.input_tokens,
                "output_tokens": AnalystUsage.output_tokens + statement.excluded.output_tokens,
                "usd_estimate": AnalystUsage.usd_estimate + statement.excluded.usd_estimate,
                "runs": AnalystUsage.runs + statement.excluded.runs,
                "updated_at": datetime.now(UTC),
            },
        )
    )
    await session.flush()
    return cost


_SPEND_SQL = text(
    "SELECT u.id AS user_id, u.email, "
    "  coalesce(sum(a.usd_estimate) FILTER (WHERE a.source = 'chat'), 0) AS chat_usd, "
    "  coalesce(sum(a.usd_estimate) FILTER (WHERE a.source <> 'chat'), 0) AS job_usd, "
    "  coalesce(sum(a.usd_estimate), 0) AS total_usd, "
    "  coalesce(sum(a.runs), 0) AS runs, "
    "  coalesce(sum(a.input_tokens), 0) AS input_tokens, "
    "  coalesce(sum(a.output_tokens), 0) AS output_tokens "
    "FROM analyst_usage a JOIN app_user u ON u.id = a.user_id "
    "WHERE a.day = :d GROUP BY u.id, u.email ORDER BY total_usd DESC, u.id"
)


async def spend_by_user(session: AsyncSession, day: date) -> list[UserSpend]:
    rows = (await session.execute(_SPEND_SQL, {"d": day})).mappings().all()
    return [
        UserSpend(
            user_id=int(row["user_id"]),
            email=str(row["email"]),
            chat_usd=Decimal(str(row["chat_usd"])),
            job_usd=Decimal(str(row["job_usd"])),
            total_usd=Decimal(str(row["total_usd"])),
            runs=int(row["runs"]),
            input_tokens=int(row["input_tokens"]),
            output_tokens=int(row["output_tokens"]),
        )
        for row in rows
    ]


async def day_spend(
    session: AsyncSession, settings: Settings, *, now: datetime | None = None
) -> GlobalSpend:
    day = today(now)
    users = await spend_by_user(session, day)
    return GlobalSpend(
        day=day,
        spend_usd=sum((row.total_usd for row in users), Decimal(0)),
        ceiling_usd=Decimal(str(settings.analyst_daily_usd_global)),
        users=users,
    )


async def maybe_alert_global_budget(
    session: AsyncSession, sender: Any, settings: Settings, *, now: datetime | None = None
) -> int:
    """Email the admins the first time the day crosses the warning line, and only then.

    Deduped on the day, not on a cooling-off timer: crossing 80% is one event with one
    email, and the same fraction re-read on every run afterwards is the same event.
    """
    from lotscope.budget.notify import send_global_budget_alert

    spend = await day_spend(session, settings, now=now)
    if spend.fraction < settings.analyst_global_alert_fraction:
        return 0
    return await send_global_budget_alert(session, sender, settings, spend, now=now)
