from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.admin.models import JobRun
from lotscope.core.market import MARKET_CODE, MARKET_NAME
from lotscope.ingestion.loaders.sheriff_civilview import CivilViewListRow, CivilViewSheriffSource
from lotscope.ingestion.models import DatasetFreshness
from lotscope.ingestion.reconciliation import to_parcel_key
from lotscope.ops.cadence import FreshnessInput, cadence_for, evaluate_freshness
from lotscope.ops.cron_schedule import CRON_SCHEDULE, missed_since
from lotscope.ops.models import MarketStats
from lotscope.ops.schemas import (
    CoverageStats,
    DatasetHealth,
    FleetMarketRow,
    FleetOverview,
    HealthRollup,
    JobRunRow,
    MarketHealthDetail,
    SheriffCoverage,
)
from lotscope.parcels.models import Parcel
from lotscope.zoning.models import ZoningStandard

LAUNCH_STATUS = "live"

_AUTOMATED_CADENCES = frozenset({"daily", "weekly"})
_FAILED = "failed"
_SHERIFF_COVERAGE_SAMPLE = 12


def summarize_sheriff_coverage(
    rows: list[CivilViewListRow],
    existing_keys: set[str],
    *,
    market_code: str,
    checked_at: datetime,
) -> SheriffCoverage:
    keys: set[str] = set()
    without_opa = 0
    for row in rows:
        key = to_parcel_key(row.opa_number, market=market_code)
        if key is None:
            without_opa += 1
        else:
            keys.add(key)
    reconciled_keys = keys & existing_keys
    unreconciled_keys = keys - existing_keys
    coverage_pct = round(len(reconciled_keys) / len(keys) * 100, 1) if keys else None
    return SheriffCoverage(
        market_code=market_code,
        total_listings=len(rows),
        with_opa=len(rows) - without_opa,
        without_opa=without_opa,
        unique_parcels=len(keys),
        reconciled=len(reconciled_keys),
        unreconciled=len(unreconciled_keys),
        coverage_pct=coverage_pct,
        sample_unreconciled=sorted(unreconciled_keys)[:_SHERIFF_COVERAGE_SAMPLE],
        checked_at=checked_at,
    )


async def sheriff_sale_coverage(
    session: AsyncSession,
    source: CivilViewSheriffSource,
    *,
    market_code: str,
    checked_at: datetime,
) -> SheriffCoverage:
    rows = await source.fetch_list()
    candidate_keys = {
        key
        for row in rows
        if (key := to_parcel_key(row.opa_number, market=market_code)) is not None
    }
    existing_keys: set[str] = set()
    if candidate_keys:
        result = await session.execute(
            select(Parcel.parcel_number).where(Parcel.parcel_number.in_(candidate_keys))
        )
        existing_keys = set(result.scalars().all())
    return summarize_sheriff_coverage(
        rows, existing_keys, market_code=market_code, checked_at=checked_at
    )


def _rollup(healths: list[DatasetHealth]) -> HealthRollup:
    red = sum(1 for h in healths if h.freshness == "red")
    amber = sum(1 for h in healths if h.freshness == "amber")
    green = sum(1 for h in healths if h.freshness == "green")
    if not healths:
        status = "unknown"
    elif red:
        status = "red"
    elif amber:
        status = "amber"
    else:
        status = "green"
    return HealthRollup(status=status, red=red, amber=amber, green=green)


def _coverage(stats: MarketStats | None) -> CoverageStats:
    if stats is None:
        return CoverageStats(
            parcel_count=None,
            geometry_pct=None,
            screened_pct=None,
            vacant_count=None,
            vacant_priced_pct=None,
            computed_at=None,
        )
    return CoverageStats(
        parcel_count=stats.parcel_count,
        geometry_pct=float(stats.geometry_pct) if stats.geometry_pct is not None else None,
        screened_pct=float(stats.screened_pct) if stats.screened_pct is not None else None,
        vacant_count=stats.vacant_count,
        vacant_priced_pct=(
            float(stats.vacant_priced_pct) if stats.vacant_priced_pct is not None else None
        ),
        computed_at=stats.computed_at,
    )


async def _dataset_healths(
    session: AsyncSession, market_code: str, now: datetime
) -> list[DatasetHealth]:
    rows = (
        await session.execute(
            select(DatasetFreshness)
            .where(DatasetFreshness.market_code == market_code)
            .order_by(DatasetFreshness.dataset)
        )
    ).scalars()
    healths: list[DatasetHealth] = []
    for row in rows:
        cadence = cadence_for(market_code, row.dataset)
        verdict = evaluate_freshness(
            FreshnessInput(
                status=row.status,
                last_success_at=row.last_success_at,
                last_attempt_at=row.last_attempt_at,
                data_vintage=row.data_vintage,
            ),
            cadence,
            now,
        )
        healths.append(
            DatasetHealth(
                dataset=row.dataset,
                cadence=cadence.kind,
                freshness=verdict.status,
                reason=verdict.reason,
                data_vintage=row.data_vintage,
                vintage_reason=verdict.vintage_reason,
                ingest_status=row.status,
                last_success_at=row.last_success_at,
                last_attempt_at=row.last_attempt_at,
                row_count=row.row_count,
            )
        )
    return healths


async def _last_ingest_at(session: AsyncSession, market_code: str) -> datetime | None:
    return await session.scalar(
        select(func.max(DatasetFreshness.last_success_at)).where(
            DatasetFreshness.market_code == market_code
        )
    )


async def _zoning_counts(session: AsyncSession, market_code: str) -> tuple[int, int]:
    standards = await session.scalar(
        select(func.count())
        .select_from(ZoningStandard)
        .where(ZoningStandard.market_code == market_code)
    )
    districts = await session.scalar(
        select(func.count(func.distinct(ZoningStandard.code))).where(
            ZoningStandard.market_code == market_code
        )
    )
    return int(standards or 0), int(districts or 0)


async def fleet_overview(session: AsyncSession, now: datetime, git_sha: str) -> FleetOverview:
    healths = await _dataset_healths(session, MARKET_CODE, now)
    standards, _ = await _zoning_counts(session, MARKET_CODE)
    rows = [
        FleetMarketRow(
            market_code=MARKET_CODE,
            name=MARKET_NAME,
            launch_status=LAUNCH_STATUS,
            health=_rollup(healths),
            coverage=_coverage(await session.get(MarketStats, MARKET_CODE)),
            last_ingest_at=await _last_ingest_at(session, MARKET_CODE),
            zoning_standard_count=standards,
        )
    ]
    return FleetOverview(markets=rows, git_sha=git_sha, generated_at=now)


async def _recent_jobs(session: AsyncSession, market_code: str, limit: int) -> list[JobRunRow]:
    failed_first = case((JobRun.status == _FAILED, 0), else_=1)
    rows = (
        await session.execute(
            select(JobRun)
            .where((JobRun.market_code == market_code) | (JobRun.market_code.is_(None)))
            .order_by(failed_first, JobRun.id.desc())
            .limit(limit)
        )
    ).scalars()
    return [JobRunRow.model_validate(row) for row in rows]


async def market_health(
    session: AsyncSession, market_code: str, now: datetime, *, job_limit: int = 20
) -> MarketHealthDetail | None:
    if market_code != MARKET_CODE:
        return None
    healths = await _dataset_healths(session, market_code, now)
    stats = await session.get(MarketStats, market_code)
    standards, districts = await _zoning_counts(session, market_code)
    return MarketHealthDetail(
        market_code=MARKET_CODE,
        name=MARKET_NAME,
        launch_status=LAUNCH_STATUS,
        coverage_note=None,
        health=_rollup(healths),
        datasets=healths,
        coverage=_coverage(stats),
        zoning_standard_count=standards,
        zoning_district_count=districts,
        recent_jobs=await _recent_jobs(session, market_code, job_limit),
        generated_at=now,
    )


@dataclass(frozen=True)
class StaleDataset:
    market_code: str
    dataset: str
    reason: str


async def stale_automated_datasets(
    session: AsyncSession, now: datetime | None = None
) -> list[StaleDataset]:
    moment = now or datetime.now(UTC)
    rows = (
        await session.execute(
            select(DatasetFreshness).order_by(
                DatasetFreshness.market_code, DatasetFreshness.dataset
            )
        )
    ).scalars()
    stale: list[StaleDataset] = []
    for row in rows:
        cadence = cadence_for(row.market_code, row.dataset)
        if cadence.kind not in _AUTOMATED_CADENCES:
            continue
        verdict = evaluate_freshness(
            FreshnessInput(
                status=row.status,
                last_success_at=row.last_success_at,
                last_attempt_at=row.last_attempt_at,
            ),
            cadence,
            moment,
        )
        if verdict.status == "red":
            stale.append(
                StaleDataset(
                    market_code=row.market_code, dataset=row.dataset, reason=verdict.reason
                )
            )
    return stale


@dataclass(frozen=True)
class StaleJob:
    name: str
    reason: str


async def stale_cron_jobs(session: AsyncSession, now: datetime | None = None) -> list[StaleJob]:
    """Crons that have not succeeded across their last two scheduled runs.

    Two runs back rather than one, because a job that is mid-flight or that lost a single
    night to a deploy is not a job that has stopped. Two consecutive misses is a job that
    is not coming back on its own.

    A cron is judged only against history we actually have. Nothing is reported as stale
    for a window that predates the oldest recorded cron run — after a fresh deployment
    that would be every job on the timetable, which is an alarm about our own record
    keeping rather than about the jobs.
    """
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    history_start = await session.scalar(
        select(func.min(JobRun.started_at)).where(JobRun.kind == "cron")
    )
    rows = (
        await session.execute(
            select(JobRun.job_id, func.max(JobRun.started_at))
            .where(JobRun.kind == "cron", JobRun.status == "success")
            .group_by(JobRun.job_id)
        )
    ).all()
    last_success: dict[str, datetime | None] = {str(job_id): at for job_id, at in rows}

    stale: list[StaleJob] = []
    for spec in CRON_SCHEDULE:
        cutoff = missed_since(spec, moment)
        if cutoff is None:
            continue
        if history_start is None or cutoff < history_start.astimezone(UTC):
            continue
        succeeded_at = last_success.get(f"cron:{spec.name}")
        if succeeded_at is None:
            stale.append(StaleJob(spec.name, "has never recorded a successful run"))
        elif succeeded_at.astimezone(UTC) < cutoff:
            stale.append(
                StaleJob(
                    spec.name,
                    "last succeeded "
                    f"{succeeded_at.astimezone(UTC).strftime('%Y-%m-%d %H:%M')} UTC, "
                    f"two scheduled runs ago was {cutoff.strftime('%Y-%m-%d %H:%M')} UTC",
                )
            )
    return stale
