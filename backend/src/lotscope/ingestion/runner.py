from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.core.logging import get_logger
from lotscope.ingestion.errors import IngestionError
from lotscope.ingestion.service import record_freshness

Loader = Callable[[AsyncSession], Awaitable[int]]

_logger = get_logger("ingestion.runner")


async def run_loader(
    session_factory: async_sessionmaker[AsyncSession],
    loader: Loader,
    *,
    dataset: str,
) -> int:
    try:
        async with session_factory() as session:
            total = await loader(session)
            await session.commit()
    except Exception as exc:
        _logger.error("ingestion_failed", dataset=dataset, error=str(exc))
        async with session_factory() as session:
            await record_freshness(session, dataset, status="failed", detail=str(exc))
            await session.commit()
        raise IngestionError(f"ingestion failed for {dataset}: {exc}") from exc
    _logger.info("ingestion_succeeded", dataset=dataset, rows=total)
    return total
