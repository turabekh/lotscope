from typing import Any

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.models import DatasetFreshness
from lotscope.ingestion.upsert import upsert


async def record_freshness(
    session: AsyncSession,
    dataset: str,
    *,
    status: str,
    success: bool = False,
    row_count: int | None = None,
    detail: str | None = None,
) -> None:
    row: dict[str, Any] = {
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
    await upsert(session, DatasetFreshness, [row], index_elements=["dataset"])
