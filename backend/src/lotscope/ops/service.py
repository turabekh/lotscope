from datetime import datetime

from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.admin.models import JobRun
from lotscope.ingestion.models import DatasetFreshness
from lotscope.markets.capabilities import market_capability_notes, market_display_name
from lotscope.markets.models import Market
from lotscope.ops.cadence import FreshnessInput, cadence_for, evaluate_freshness
from lotscope.ops.models import MarketStats
from lotscope.ops.schemas import (
    CapabilityNote,
    CoverageStats,
    DatasetHealth,
    FleetMarketRow,
    FleetOverview,
    HealthRollup,
    JobRunRow,
    MarketHealthDetail,
    VerdictVersionCount,
)
from lotscope.zoning.models import ZoningStandard

_FAILED = "failed"


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
            verdict_pct=None,
            vacant_count=None,
            vacant_with_comp_pct=None,
            computed_at=None,
        )
    return CoverageStats(
        parcel_count=stats.parcel_count,
        geometry_pct=float(stats.geometry_pct) if stats.geometry_pct is not None else None,
        verdict_pct=float(stats.verdict_pct) if stats.verdict_pct is not None else None,
        vacant_count=stats.vacant_count,
        vacant_with_comp_pct=(
            float(stats.vacant_with_comp_pct) if stats.vacant_with_comp_pct is not None else None
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


async def fleet_overview(session: AsyncSession, now: datetime) -> FleetOverview:
    markets = (await session.execute(select(Market).order_by(Market.code))).scalars().all()
    stats_by_market = {
        s.market_code: s for s in (await session.execute(select(MarketStats))).scalars()
    }
    rows: list[FleetMarketRow] = []
    for market in markets:
        healths = await _dataset_healths(session, market.code, now)
        standards, _ = await _zoning_counts(session, market.code)
        rows.append(
            FleetMarketRow(
                market_code=market.code,
                name=market.name,
                launch_status=market.launch_status,
                health=_rollup(healths),
                coverage=_coverage(stats_by_market.get(market.code)),
                last_ingest_at=await _last_ingest_at(session, market.code),
                zoning_standard_count=standards,
            )
        )
    return FleetOverview(markets=rows, generated_at=now)


async def _verdict_versions(session: AsyncSession, market_code: str) -> list[VerdictVersionCount]:
    sql = text(
        "SELECT v.verdict_version AS version, count(*) AS n "
        "FROM parcel p LEFT JOIN parcel_verdict v ON v.parcel_number = p.parcel_number "
        "WHERE p.market_code = :market "
        "GROUP BY v.verdict_version ORDER BY n DESC"
    )
    result = await session.execute(sql, {"market": market_code})
    return [VerdictVersionCount(verdict_version=row.version, count=int(row.n)) for row in result]


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
    market = await session.get(Market, market_code)
    if market is None:
        return None
    healths = await _dataset_healths(session, market_code, now)
    stats = await session.get(MarketStats, market_code)
    standards, districts = await _zoning_counts(session, market_code)
    capabilities = [
        CapabilityNote(category=category, state=state, detail=detail)
        for category, state, detail in market_capability_notes(market_code)
    ]
    return MarketHealthDetail(
        market_code=market.code,
        name=market.name or market_display_name(market.code),
        launch_status=market.launch_status,
        coverage_note=market.coverage_note,
        health=_rollup(healths),
        datasets=healths,
        coverage=_coverage(stats),
        zoning_standard_count=standards,
        zoning_district_count=districts,
        capabilities=capabilities,
        verdict_versions=await _verdict_versions(session, market_code),
        recent_jobs=await _recent_jobs(session, market_code, job_limit),
        generated_at=now,
    )
