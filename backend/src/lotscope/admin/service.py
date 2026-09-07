from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.accounts.schemas import UserRead
from lotscope.admin.catalog import CATALOG, CATALOG_BY_ID, storable_params
from lotscope.admin.models import JobRun
from lotscope.admin.schemas import (
    AdminOverview,
    AdminUsersResponse,
    AdminUserUpdate,
    AnalystSpendRow,
    AnalystSpendToday,
    DatasetStatus,
    JobCatalogEntry,
    JobParamSpec,
    JobRunSummary,
)
from lotscope.budget.service import day_spend, user_ceilings
from lotscope.core.config import Settings
from lotscope.core.errors import ConflictError, NotFoundError
from lotscope.ingestion.models import DatasetFreshness

_ACTIVE_STATUSES = ("queued", "running")
_ERROR_LIMIT = 2000


class JobEnqueuer(Protocol):
    async def enqueue_job(self, function: str, *args: Any, **kwargs: Any) -> Any: ...


_COUNTS_SQL = text(
    "SELECT "
    "(SELECT count(*) FROM parcel) AS parcels_total, "
    "(SELECT count(*) FROM parcel WHERE coalesce(is_vacant, false)) AS parcels_vacant, "
    "(SELECT count(*) FROM parcel_screen) AS screened_total, "
    "(SELECT count(*) FROM deed_document) AS deeds_total, "
    "(SELECT count(*) FROM neighborhood) AS neighborhoods_total"
)


async def list_datasets(session: AsyncSession) -> list[DatasetStatus]:
    rows = (
        await session.execute(
            select(DatasetFreshness).order_by(
                DatasetFreshness.market_code, DatasetFreshness.dataset
            )
        )
    ).scalars()
    return [DatasetStatus.model_validate(row) for row in rows]


async def platform_overview(session: AsyncSession) -> AdminOverview:
    counts = (await session.execute(_COUNTS_SQL)).one()
    by_tier_rows = (
        await session.execute(select(User.tier, func.count()).group_by(User.tier))
    ).all()
    by_tier = {tier: int(count) for tier, count in by_tier_rows}
    return AdminOverview(
        users_total=sum(by_tier.values()),
        users_by_tier=by_tier,
        parcels_total=int(counts.parcels_total or 0),
        parcels_vacant=int(counts.parcels_vacant or 0),
        screened_total=int(counts.screened_total or 0),
        deeds_total=int(counts.deeds_total or 0),
        neighborhoods_total=int(counts.neighborhoods_total or 0),
    )


async def list_users(
    session: AsyncSession, *, limit: int = 50, offset: int = 0
) -> AdminUsersResponse:
    total = int(await session.scalar(select(func.count()).select_from(User)) or 0)
    rows = (
        await session.execute(
            select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
        )
    ).scalars()
    return AdminUsersResponse(total=total, users=[UserRead.model_validate(row) for row in rows])


async def update_user(session: AsyncSession, user_id: int, data: AdminUserUpdate) -> UserRead:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} was not found.")
    if data.role is not None:
        user.role = data.role
    if data.tier is not None:
        user.tier = data.tier
    if data.is_active is not None:
        user.is_active = data.is_active
    # Explicit null means "back to the platform default", so what was sent decides, not
    # whether the value happens to be None.
    if "analyst_daily_usd" in data.model_fields_set:
        user.analyst_daily_usd = data.analyst_daily_usd
    if "analyst_daily_runs" in data.model_fields_set:
        user.analyst_daily_runs = data.analyst_daily_runs
    await session.flush()
    return UserRead.model_validate(user)


async def analyst_spend_today(
    session: AsyncSession, settings: Settings, *, now: datetime | None = None
) -> AnalystSpendToday:
    """Today's model spend, per buyer, against the ceiling each of them is actually on."""
    spend = await day_spend(session, settings, now=now)
    users = (
        {
            user.id: user
            for user in (
                await session.execute(
                    select(User).where(User.id.in_([row.user_id for row in spend.users]))
                )
            )
            .scalars()
            .all()
        }
        if spend.users
        else {}
    )

    rows: list[AnalystSpendRow] = []
    for row in spend.users:
        account = users.get(row.user_id)
        usd_ceiling, run_ceiling = (
            user_ceilings(account, settings)
            if account is not None
            else (
                Decimal(str(settings.analyst_daily_usd_per_user)),
                int(settings.analyst_daily_runs_per_user),
            )
        )
        rows.append(
            AnalystSpendRow(
                user_id=row.user_id,
                email=row.email,
                chat_usd=row.chat_usd,
                job_usd=row.job_usd,
                total_usd=row.total_usd,
                runs=row.runs,
                input_tokens=row.input_tokens,
                output_tokens=row.output_tokens,
                ceiling_usd=usd_ceiling,
                run_ceiling=run_ceiling,
                over_ceiling=row.chat_usd >= usd_ceiling,
            )
        )
    return AnalystSpendToday(
        day=spend.day,
        spend_usd=spend.spend_usd,
        global_ceiling_usd=spend.ceiling_usd,
        fraction=round(spend.fraction, 4),
        default_ceiling_usd=Decimal(str(settings.analyst_daily_usd_per_user)),
        default_run_ceiling=int(settings.analyst_daily_runs_per_user),
        users=rows,
    )


def _run_summary(run: JobRun | None) -> JobRunSummary | None:
    return JobRunSummary.model_validate(run) if run is not None else None


async def _latest_runs_by_job(session: AsyncSession) -> dict[str, JobRun]:
    rows = (
        await session.execute(
            select(JobRun).order_by(JobRun.job_id, JobRun.id.desc()).distinct(JobRun.job_id)
        )
    ).scalars()
    return {run.job_id: run for run in rows}


def _newest(*runs: JobRun | None) -> JobRun | None:
    """The run that started most recently, counting a queued one as newest.

    A job is run two ways and recorded under two ids — by hand under `spec.id`, by the
    timetable under `cron:<cron_name>` — and the console wants the last time it ran,
    whichever did it.
    """
    found = [run for run in runs if run is not None]
    if not found:
        return None
    return max(found, key=lambda run: (run.started_at or run.created_at, run.id))


async def job_catalog(session: AsyncSession) -> list[JobCatalogEntry]:
    latest = await _latest_runs_by_job(session)
    return [
        JobCatalogEntry(
            id=spec.id,
            label=spec.label,
            kind=spec.kind,
            description=spec.description,
            market=spec.market,
            dataset=spec.dataset,
            params=[
                JobParamSpec(name=p.name, label=p.label, type=p.type, required=p.required)
                for p in spec.params
            ],
            latest_run=_run_summary(
                _newest(
                    latest.get(spec.id),
                    latest.get(f"cron:{spec.cron_name}") if spec.cron_name else None,
                )
            ),
        )
        for spec in CATALOG
    ]


async def list_job_runs(session: AsyncSession, *, limit: int = 50) -> list[JobRunSummary]:
    rows = (await session.execute(select(JobRun).order_by(JobRun.id.desc()).limit(limit))).scalars()
    return [JobRunSummary.model_validate(row) for row in rows]


async def enqueue_job(
    session: AsyncSession,
    enqueuer: JobEnqueuer,
    *,
    job_id: str,
    triggered_by: int,
    params: dict[str, str] | None = None,
) -> JobRunSummary:
    spec = CATALOG_BY_ID.get(job_id)
    if spec is None:
        raise NotFoundError(f"Job {job_id!r} is not in the catalog.")
    stored = storable_params(spec, params or {})
    # Both ids, because the nightly and the button run the same job over the same tables:
    # starting a second `recompute_distress` on top of the 08:00 one is two passes over
    # every parcel at once. The console already refuses it — the API has to agree.
    ids = [spec.id] + ([f"cron:{spec.cron_name}"] if spec.cron_name else [])
    active = await session.scalar(
        select(JobRun.job_id)
        .where(JobRun.job_id.in_(ids), JobRun.status.in_(_ACTIVE_STATUSES))
        .limit(1)
    )
    if active is not None:
        raise ConflictError(
            f"Job {job_id!r} already has a run in progress."
            if active == spec.id
            else f"Job {job_id!r} is running now as the scheduled {spec.cron_name!r}."
        )
    run = JobRun(
        job_id=spec.id,
        label=spec.label,
        kind=spec.kind,
        market_code=spec.market,
        params=stored or None,
        status="queued",
        triggered_by=triggered_by,
    )
    session.add(run)
    await session.flush()
    arq_job = await enqueuer.enqueue_job("run_admin_job", run.id)
    run.arq_job_id = getattr(arq_job, "job_id", None)
    await session.flush()
    return JobRunSummary.model_validate(run)


async def mark_job_running(session: AsyncSession, job_run_id: int) -> JobRun:
    run = await session.get(JobRun, job_run_id)
    if run is None:
        raise NotFoundError(f"Job run {job_run_id} was not found.")
    run.status = "running"
    run.started_at = datetime.now(UTC)
    await session.flush()
    return run


INTERRUPTED_STATUS = "interrupted"
_INTERRUPTED_ERROR = (
    "The worker process that was running this job stopped before it could write a result. "
    "Recorded as interrupted when the worker next started."
)


async def reap_orphaned_runs(session: AsyncSession) -> int:
    """Close every run that says it is running while nobody is running it.

    Only the process that opened a `job_run` row ever closes it, so a worker that dies
    without a chance to write — a container recreated under a deploy, an OOM kill, a hard
    restart — leaves the row saying `running` for ever. Nothing later contradicts it: the
    next night's run opens its own row, and the stale one sits there claiming a job is in
    flight months after the process that claimed it stopped existing.

    This runs at worker startup, where the claim is decidable. One worker serves this
    deployment, so at the moment it starts nothing it owns can be running yet, and every
    row still marked running belongs to a process that is gone. `queued` rows are left
    alone: those are waiting in Redis, which survives a restart, and the worker is about
    to pick them up.
    """
    orphans = (
        (await session.execute(select(JobRun).where(JobRun.status == "running"))).scalars().all()
    )
    now = datetime.now(UTC)
    for run in orphans:
        run.status = INTERRUPTED_STATUS
        run.finished_at = now
        run.error = _INTERRUPTED_ERROR
    await session.flush()
    return len(orphans)


async def mark_job_finished(
    session: AsyncSession,
    job_run_id: int,
    *,
    status: str,
    result_count: int | None = None,
    error: str | None = None,
) -> JobRun:
    run = await session.get(JobRun, job_run_id)
    if run is None:
        raise NotFoundError(f"Job run {job_run_id} was not found.")
    finished = datetime.now(UTC)
    run.status = status
    run.result_count = result_count
    run.error = error[:_ERROR_LIMIT] if error is not None else None
    run.finished_at = finished
    if run.started_at is not None:
        run.duration_ms = int((finished - run.started_at).total_seconds() * 1000)
    await session.flush()
    return run
