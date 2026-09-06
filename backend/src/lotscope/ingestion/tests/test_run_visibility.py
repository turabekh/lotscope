"""The deploy guard's one question: is an ingest in flight right now?

It reads `ingest_run`, so the row has to exist and say `running` while the load is still
going. It used to be written inside the load's own transaction, which meant nobody could
see it until the load had finished — the guard read clean through every ingest, and a
deploy at 04:30 killed two datasets on 2026-08-24.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from lotscope.ingestion.errors import IngestionError
from lotscope.ingestion.runner import run_loader

pytestmark = pytest.mark.integration


async def test_the_run_row_is_visible_to_another_session_before_the_load_commits(
    migrated_database: str,
) -> None:
    engine = create_async_engine(migrated_database)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    seen: list[tuple[str, str]] = []

    async def loader(session: AsyncSession, run_id: int) -> int:
        # Work the load does inside its own uncommitted transaction.
        await session.execute(text("SELECT 1"))
        # A second session — the deploy guard is a psql on the other side of the wire.
        async with factory() as observer:
            rows = (
                await observer.execute(
                    text("SELECT dataset, status FROM ingest_run WHERE id = :id"),
                    {"id": run_id},
                )
            ).all()
            seen.extend((row.dataset, row.status) for row in rows)
        return 7

    try:
        total = await run_loader(factory, loader, dataset="visibility_probe")
        assert total == 7
        assert seen == [("visibility_probe", "running")]

        async with factory() as session:
            row = (
                await session.execute(
                    text(
                        "SELECT status, finished_at FROM ingest_run "
                        "WHERE dataset = 'visibility_probe'"
                    )
                )
            ).one()
        assert row.status == "success"
        assert row.finished_at is not None
    finally:
        async with factory() as session:
            await session.execute(text("DELETE FROM ingest_run WHERE dataset = 'visibility_probe'"))
            await session.commit()
        await engine.dispose()


async def test_a_loader_that_raises_leaves_the_row_failed_not_running(
    migrated_database: str,
) -> None:
    engine = create_async_engine(migrated_database)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def loader(session: AsyncSession, run_id: int) -> int:
        raise RuntimeError("upstream returned nonsense")

    try:
        with pytest.raises(IngestionError):
            await run_loader(factory, loader, dataset="failure_probe")

        async with factory() as session:
            row = (
                await session.execute(
                    text(
                        "SELECT status, finished_at FROM ingest_run WHERE dataset = 'failure_probe'"
                    )
                )
            ).one()
        # A row left saying "running" would block every deploy for the next four hours.
        assert row.status == "failed"
        assert row.finished_at is not None
    finally:
        async with factory() as session:
            await session.execute(text("DELETE FROM ingest_run WHERE dataset = 'failure_probe'"))
            await session.execute(
                text("DELETE FROM dataset_freshness WHERE dataset = 'failure_probe'")
            )
            await session.commit()
        await engine.dispose()
