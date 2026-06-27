import asyncio
import os
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)

from lotscope.core.config import get_settings

_TEST_DB_IMAGE = "lotscope/postgres:test"


def _start_postgis() -> Iterator[str]:
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers is not installed")

    try:
        container = PostgresContainer(
            _TEST_DB_IMAGE,
            username="lotscope",
            password="lotscope",
            dbname="lotscope",
        )
        container.start()
    except Exception as exc:
        pytest.skip(f"docker is not available for integration tests: {exc}")

    try:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(5432)
        yield f"postgresql+asyncpg://lotscope:lotscope@{host}:{port}/lotscope"
    finally:
        container.stop()


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    yield from _start_postgis()


@pytest.fixture(scope="session")
def migrated_database(database_url: str) -> str:
    async def ensure_postgis() -> None:
        engine = create_async_engine(database_url)
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await engine.dispose()

    asyncio.run(ensure_postgis())
    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()
    command.upgrade(Config("alembic.ini"), "head")
    return database_url


@pytest_asyncio.fixture
async def db_connection(migrated_database: str) -> AsyncIterator[AsyncConnection]:
    engine: AsyncEngine = create_async_engine(migrated_database)
    connection = await engine.connect()
    transaction = await connection.begin()
    try:
        yield connection
    finally:
        await transaction.rollback()
        await connection.close()
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(migrated_database: str) -> AsyncIterator[AsyncSession]:
    engine: AsyncEngine = create_async_engine(migrated_database)
    connection = await engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()
        await engine.dispose()
