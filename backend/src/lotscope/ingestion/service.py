from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.provenance import datasets_for_source, oldest_as_of
from lotscope.ingestion.models import DatasetFreshness
from lotscope.ingestion.upsert import upsert


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
) -> None:
    row: dict[str, Any] = {
        "market_code": market_code,
        "dataset": dataset,
        "status": status,
        "last_attempt_at": func.now(),
    }
    if success:
        row["last_success_at"] = func.now()
    if row_count is not None:
        row["row_count"] = row_count
    if detail is not None:
        row["detail"] = detail
    await upsert(session, DatasetFreshness, [row], index_elements=["market_code", "dataset"])


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


async def source_freshness(session: AsyncSession, market_code: str) -> list[dict[str, Any]]:
    last_success = await dataset_last_success(session, market_code)
    return [
        {
            "source_label": label,
            "title": title,
            "as_of": source_as_of(label, last_success),
            "datasets": list(datasets_for_source(label)),
        }
        for label, title in _FRESHNESS_SURFACES
    ]
