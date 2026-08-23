from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.provenance import datasets_for_source, oldest_as_of
from lotscope.ingestion.models import DatasetFreshness
from lotscope.ingestion.upsert import upsert
from lotscope.ops.cadence import (
    FreshnessInput,
    FreshnessVerdict,
    cadence_for,
    evaluate_freshness,
)


async def dataset_last_success(session: AsyncSession, market_code: str) -> dict[str, datetime]:
    result = await session.execute(
        select(DatasetFreshness.dataset, DatasetFreshness.last_success_at).where(
            DatasetFreshness.market_code == market_code,
            DatasetFreshness.last_success_at.is_not(None),
        )
    )
    return {row[0]: row[1] for row in result}


def source_as_of(source_label: str, last_success: dict[str, datetime]) -> datetime | None:
    datasets = datasets_for_source(source_label)
    if not datasets:
        return None
    return oldest_as_of([last_success.get(dataset) for dataset in datasets])


async def record_freshness(
    session: AsyncSession,
    dataset: str,
    *,
    status: str,
    market_code: str = "phl",
    success: bool = False,
    row_count: int | None = None,
    detail: str | None = None,
    data_vintage: date | None = None,
    unless_succeeded_after: datetime | None = None,
) -> None:
    row: dict[str, Any] = {
        "market_code": market_code,
        "dataset": dataset,
        "status": status,
        "last_attempt_at": func.clock_timestamp(),
    }
    if success:
        row["last_success_at"] = func.clock_timestamp()
    if row_count is not None:
        row["row_count"] = row_count
    if detail is not None:
        row["detail"] = detail
    elif success:
        row["detail"] = None
    if data_vintage is not None:
        row["data_vintage"] = data_vintage
    not_superseded_by_a_newer_success = (
        None
        if unless_succeeded_after is None
        else or_(
            DatasetFreshness.last_success_at.is_(None),
            DatasetFreshness.last_success_at < unless_succeeded_after,
        )
    )
    await upsert(
        session,
        DatasetFreshness,
        [row],
        index_elements=["market_code", "dataset"],
        where=not_superseded_by_a_newer_success,
    )


_FRESHNESS_SURFACES: tuple[tuple[str, str], ...] = (
    ("parcel", "Parcel geometry & ownership"),
    ("opa_properties_public", "Assessment"),
    ("zoning_district", "Zoning districts"),
    ("rtt_summary", "Recorded sales"),
    ("li_event", "Code & permit events"),
    ("tax_status", "Tax status"),
    ("flood_zone", "Flood zones"),
    ("street_centerline", "Street access"),
)


_WORST_FIRST: tuple[str, ...] = ("red", "amber", "green")


async def source_freshness(
    session: AsyncSession, market_code: str, now: datetime | None = None
) -> list[dict[str, Any]]:
    moment = now or datetime.now(UTC)
    last_success = await dataset_last_success(session, market_code)
    rows = (
        await session.execute(
            select(DatasetFreshness).where(DatasetFreshness.market_code == market_code)
        )
    ).scalars()
    by_dataset = {row.dataset: row for row in rows}
    surfaces: list[dict[str, Any]] = []
    for label, title in _FRESHNESS_SURFACES:
        datasets = list(datasets_for_source(label))
        verdict = _worst_verdict(market_code, datasets, by_dataset, moment)
        surfaces.append(
            {
                "source_label": label,
                "title": title,
                "as_of": source_as_of(label, last_success),
                "datasets": datasets,
                "freshness": verdict.status if verdict else None,
                "freshness_reason": verdict.reason if verdict else None,
                "data_vintage": _oldest_vintage(datasets, by_dataset),
            }
        )
    return surfaces


def _oldest_vintage(datasets: list[str], by_dataset: dict[str, DatasetFreshness]) -> date | None:
    vintages = [
        row.data_vintage
        for dataset in datasets
        if (row := by_dataset.get(dataset)) is not None and row.data_vintage is not None
    ]
    return min(vintages) if vintages else None


def _worst_verdict(
    market_code: str,
    datasets: list[str],
    by_dataset: dict[str, DatasetFreshness],
    now: datetime,
) -> FreshnessVerdict | None:
    verdicts = [
        evaluate_freshness(
            FreshnessInput(
                status=row.status,
                last_success_at=row.last_success_at,
                last_attempt_at=row.last_attempt_at,
                data_vintage=row.data_vintage,
            ),
            cadence_for(market_code, dataset),
            now,
        )
        for dataset in datasets
        if (row := by_dataset.get(dataset)) is not None
    ]
    if not verdicts:
        return None
    return min(verdicts, key=lambda verdict: _WORST_FIRST.index(verdict.status))
