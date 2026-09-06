"""Test support for loaders that stage rows against a run.

Production opens the run row in its own committed transaction before the loader starts,
so the deploy guard can see it. A test drives the loader directly, so it opens one the
same way and hands over the id.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.models import IngestRun


async def open_run(session: AsyncSession, dataset: str) -> int:
    run = IngestRun(dataset=dataset, status="running")
    session.add(run)
    await session.flush()
    return int(run.id)
