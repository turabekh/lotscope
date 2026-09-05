from datetime import UTC, datetime
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
    DatasetStatus,
    JobCatalogEntry,
    JobParamSpec,
    JobRunSummary,
)
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
    "(SELECT count(*) FROM parcel_verdict) AS verdicts_total, "
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
        verdicts_total=int(counts.verdicts_total or 0),
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
    await session.flush()
    return UserRead.model_validate(user)


async def _latest_runs_by_job(session: AsyncSession) -> dict[str, JobRun]:
    rows = (
        await session.execute(
            select(JobRun).order_by(JobRun.job_id, JobRun.id.desc()).distinct(JobRun.job_id)
        )
    ).scalars()
    return {run.job_id: run for run in rows}


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
            latest_run=(
                JobRunSummary.model_validate(latest[spec.id]) if spec.id in latest else None
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
    active = await session.scalar(
        select(JobRun.id)
        .where(JobRun.job_id == job_id, JobRun.status.in_(_ACTIVE_STATUSES))
        .limit(1)
    )
    if active is not None:
        raise ConflictError(f"Job {job_id!r} already has a run in progress.")
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
    run.status = status
    run.result_count = result_count
    run.error = error[:_ERROR_LIMIT] if error is not None else None
    run.finished_at = datetime.now(UTC)
    await session.flush()
    return run
