from asyncio import CancelledError

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from lotscope.ingestion.errors import IngestionError
from lotscope.ingestion.models import DatasetFreshness
from lotscope.ingestion.runner import run_loader
from lotscope.ingestion.service import record_freshness

pytestmark = pytest.mark.integration


async def _cleanup(session_factory: async_sessionmaker[AsyncSession], dataset: str) -> None:
    async with session_factory() as session:
        record = await session.get(DatasetFreshness, ("phl", dataset))
        if record is not None:
            await session.delete(record)
            await session.commit()


async def test_run_loader_commits_and_returns_total(migrated_database: str) -> None:
    engine = create_async_engine(migrated_database)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def loader(session: AsyncSession, run_id: int) -> int:
        await record_freshness(session, "ds_ok", status="success", success=True, row_count=7)
        return 7

    try:
        total = await run_loader(session_factory, loader, dataset="ds_ok")
        assert total == 7
        async with session_factory() as session:
            record = await session.get(DatasetFreshness, ("phl", "ds_ok"))
            assert record is not None
            assert record.status == "success"
            assert record.row_count == 7
    finally:
        await _cleanup(session_factory, "ds_ok")
        await engine.dispose()


async def test_run_loader_records_failure_and_raises(migrated_database: str) -> None:
    engine = create_async_engine(migrated_database)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def failing(session: AsyncSession, run_id: int) -> int:
        raise ValueError("boom")

    try:
        with pytest.raises(IngestionError):
            await run_loader(session_factory, failing, dataset="ds_fail")
        async with session_factory() as session:
            record = await session.get(DatasetFreshness, ("phl", "ds_fail"))
            assert record is not None
            assert record.status == "failed"
            assert record.detail is not None
    finally:
        await _cleanup(session_factory, "ds_fail")
        await engine.dispose()


async def test_run_loader_records_a_cancelled_run_before_re_raising(
    migrated_database: str,
) -> None:
    engine = create_async_engine(migrated_database)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def cancelled(session: AsyncSession, run_id: int) -> int:
        raise CancelledError

    try:
        with pytest.raises(CancelledError):
            await run_loader(session_factory, cancelled, dataset="ds_cancelled")
        async with session_factory() as session:
            record = await session.get(DatasetFreshness, ("phl", "ds_cancelled"))
            assert record is not None
            assert record.status == "failed"
            assert "timeout" in (record.detail or "")
    finally:
        await _cleanup(session_factory, "ds_cancelled")
        await engine.dispose()


async def test_a_failure_does_not_overwrite_a_success_recorded_after_the_run_started(
    migrated_database: str,
) -> None:
    engine = create_async_engine(migrated_database)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def fails_after_a_concurrent_run_succeeds(session: AsyncSession, run_id: int) -> int:
        async with session_factory() as concurrent:
            await record_freshness(
                concurrent, "ds_race", status="success", success=True, row_count=42
            )
            await concurrent.commit()
        raise ValueError("duplicate run lost the merge")

    try:
        with pytest.raises(IngestionError):
            await run_loader(
                session_factory, fails_after_a_concurrent_run_succeeds, dataset="ds_race"
            )
        async with session_factory() as session:
            record = await session.get(DatasetFreshness, ("phl", "ds_race"))
            assert record is not None
            assert record.status == "success"
            assert record.row_count == 42
            assert record.last_success_at is not None
    finally:
        await _cleanup(session_factory, "ds_race")
        await engine.dispose()


async def test_a_failure_still_supersedes_a_success_from_before_the_run_started(
    migrated_database: str,
) -> None:
    engine = create_async_engine(migrated_database)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def failing(session: AsyncSession, run_id: int) -> int:
        raise ValueError("boom")

    try:
        async with session_factory() as session:
            await record_freshness(session, "ds_stale", status="success", success=True, row_count=9)
            await session.commit()

        with pytest.raises(IngestionError):
            await run_loader(session_factory, failing, dataset="ds_stale")

        async with session_factory() as session:
            record = await session.get(DatasetFreshness, ("phl", "ds_stale"))
            assert record is not None
            assert record.status == "failed"
            assert record.last_success_at is not None
    finally:
        await _cleanup(session_factory, "ds_stale")
        await engine.dispose()


async def test_a_failure_does_not_overwrite_a_success_whose_run_started_first(
    migrated_database: str,
) -> None:
    engine = create_async_engine(migrated_database)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    winner = session_factory()

    async def fails_after_the_longer_run_commits(session: AsyncSession, run_id: int) -> int:
        await record_freshness(winner, "ds_race_long", status="success", success=True, row_count=42)
        await winner.commit()
        raise ValueError("duplicate run lost the merge")

    try:
        await winner.execute(select(func.now()))

        with pytest.raises(IngestionError):
            await run_loader(
                session_factory, fails_after_the_longer_run_commits, dataset="ds_race_long"
            )

        async with session_factory() as session:
            record = await session.get(DatasetFreshness, ("phl", "ds_race_long"))
            assert record is not None
            assert record.status == "success"
            assert record.row_count == 42
    finally:
        await winner.close()
        await _cleanup(session_factory, "ds_race_long")
        await engine.dispose()
