from asyncio import CancelledError
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.core.logging import get_logger
from lotscope.ingestion.errors import IngestionError
from lotscope.ingestion.models import IngestRun
from lotscope.ingestion.service import record_freshness

# A loader is handed the id of the run row that was opened for it. It does not open
# its own: a row written inside the load's transaction is invisible until the load
# ends, which is no use to anything asking whether an ingest is in flight.
Loader = Callable[[AsyncSession, int], Awaitable[int]]

_logger = get_logger("ingestion.runner")


async def _database_now(session_factory: async_sessionmaker[AsyncSession]) -> datetime:
    async with session_factory() as session:
        stamp: datetime = (await session.execute(select(func.clock_timestamp()))).scalar_one()
        return stamp


async def _record_failure(
    session_factory: async_sessionmaker[AsyncSession],
    dataset: str,
    market_code: str,
    detail: str,
    run_started_at: datetime,
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


async def _open_run(session_factory: async_sessionmaker[AsyncSession], dataset: str) -> int:
    """Announce the run, committed, before any work starts.

    This is what the deploy guard reads. A loader runs its whole load in one transaction,
    so the row it used to write for itself only became visible once the load was over —
    the guard read clean through the middle of every ingest.
    """
    async with session_factory() as session:
        run = IngestRun(dataset=dataset, status="running")
        session.add(run)
        await session.commit()
        return int(run.id)


async def _close_run(
    session_factory: async_sessionmaker[AsyncSession], run_id: int, *, status: str
) -> None:
    async with session_factory() as session:
        run = await session.get(IngestRun, run_id)
        if run is None:
            return
        run.status = status
        run.finished_at = datetime.now(UTC)
        await session.commit()


async def run_loader(
    session_factory: async_sessionmaker[AsyncSession],
    loader: Loader,
    *,
    dataset: str,
    market_code: str = "phl",
) -> int:
    try:
        run_started_at = await _database_now(session_factory)
    except Exception as exc:
        _logger.error(
            "ingestion_start_stamp_failed", market=market_code, dataset=dataset, error=str(exc)
        )
        raise IngestionError(f"ingestion could not start for {dataset}: {exc}") from exc
    run_id = await _open_run(session_factory, dataset)
    try:
        async with session_factory() as session:
            total = await loader(session, run_id)
            await session.commit()
    except CancelledError:
        _logger.error("ingestion_cancelled", market=market_code, dataset=dataset)
        await _close_run(session_factory, run_id, status="failed")
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
        await _close_run(session_factory, run_id, status="failed")
        await _record_failure(session_factory, dataset, market_code, str(exc), run_started_at)
        raise IngestionError(f"ingestion failed for {dataset}: {exc}") from exc
    await _close_run(session_factory, run_id, status="success")
    _logger.info("ingestion_succeeded", dataset=dataset, rows=total)
    return total
