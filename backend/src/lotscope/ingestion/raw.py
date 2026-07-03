from collections.abc import Sequence
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.models import RawRecord
from lotscope.ingestion.upsert import batch_by_bind_limit


async def write_raw(session: AsyncSession, rows: Sequence[dict[str, Any]]) -> None:
    for batch in batch_by_bind_limit(rows):
        await session.execute(pg_insert(RawRecord).values(list(batch)))
