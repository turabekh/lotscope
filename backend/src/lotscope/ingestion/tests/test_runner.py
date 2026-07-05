import pytest
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

    async def loader(session: AsyncSession) -> int:
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

    async def failing(session: AsyncSession) -> int:
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
