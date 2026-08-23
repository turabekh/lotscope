from asyncio import CancelledError
from collections.abc import Awaitable, Callable
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.core.logging import get_logger
from lotscope.ingestion.errors import IngestionError
from lotscope.ingestion.service import record_freshness

Loader = Callable[[AsyncSession], Awaitable[int]]

_logger = get_logger("ingestion.runner")


async def _database_now(session_factory: async_sessionmaker[AsyncSession]) -> datetime:
    async with session_factory() as session:
        return (await session.execute(select(func.now()))).scalar_one()


async def _record_failure(
    session_factory: async_sessionmaker[AsyncSession],
    dataset: str,
    market_code: str,
    detail: str,
    run_started_at: datetime | None,
) -> None:
    async with session_factory() as session:
        await record_freshness(
            session,
            dataset,
            status="failed",
            market_code=market_code,
            detail=detail,
            unless_succeeded_after=run_started_at,
        )
        await session.commit()


async def run_loader(
    session_factory: async_sessionmaker[AsyncSession],
    loader: Loader,
    *,
    dataset: str,
    market_code: str = "phl",
) -> int:
    run_started_at: datetime | None = None
    try:
        run_started_at = await _database_now(session_factory)
        async with session_factory() as session:
            total = await loader(session)
            await session.commit()
    except CancelledError:
        _logger.error("ingestion_cancelled", market=market_code, dataset=dataset)
        await _record_failure(
            session_factory,
            dataset,
            market_code,
            "Cancelled before completion, most likely the worker job timeout.",
            run_started_at,
        )
        raise
    except Exception as exc:
        _logger.error("ingestion_failed", market=market_code, dataset=dataset, error=str(exc))
        await _record_failure(session_factory, dataset, market_code, str(exc), run_started_at)
        raise IngestionError(f"ingestion failed for {dataset}: {exc}") from exc
    _logger.info("ingestion_succeeded", dataset=dataset, rows=total)
    return total
