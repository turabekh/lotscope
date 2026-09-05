import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

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
    except ImportError as cause:
        raise RuntimeError(
            "testcontainers is not installed, so no integration test can run. "
            "Install the dev dependencies: `uv sync --all-extras`."
        ) from cause

    try:
        container = PostgresContainer(
            _TEST_DB_IMAGE,
            username="lotscope",
            password="lotscope",
            dbname="lotscope",
        )
        container.start()
    except Exception as cause:
        # Never skip here. A missing image used to turn the entire integration suite
        # into a green-looking SKIP; the run has to stop and say what to do instead.
        raise RuntimeError(
            f"Could not start the {_TEST_DB_IMAGE} container, so no integration test "
            f"can run. Build it first — `make test-image` — or run the suite through "
            f"`make test` / `make test-integration`, which build it for you. "
            f"Underlying error: {cause}"
        ) from cause

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


# --- skip policy -------------------------------------------------------------------------

_ALLOWLIST_PATH = Path(__file__).resolve().parents[2] / "tests-allowed-to-skip.txt"


def _allowed_to_skip() -> tuple[str, ...]:
    if not _ALLOWLIST_PATH.exists():
        return ()
    lines = []
    for raw in _ALLOWLIST_PATH.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            lines.append(line)
    return tuple(lines)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]):  # type: ignore[no-untyped-def]
    """Turn an unexpected skip into a failure.

    A skip is a test that did not run. The suite has twice reported green while the
    whole integration half of it was skipped, so skipping is opt-in per file via
    tests-allowed-to-skip.txt, and that file is empty on purpose.
    """
    outcome = yield
    report = outcome.get_result()
    if report.when != "setup" and report.outcome != "skipped":
        return
    if report.outcome != "skipped":
        return

    path = str(Path(str(item.path)).resolve())
    root = str(_ALLOWLIST_PATH.parent)
    relative = path[len(root) :].lstrip("/") if path.startswith(root) else path
    if any(relative.startswith(prefix) for prefix in _allowed_to_skip()):
        return

    reason = ""
    if isinstance(report.longrepr, tuple) and len(report.longrepr) == 3:
        reason = str(report.longrepr[2])
    report.outcome = "failed"
    report.longrepr = (
        f"{item.nodeid} was skipped, and skipping is not allowed.\n"
        f"Reason given: {reason or 'none'}\n"
        f"A skipped test is a gate that did not run. Fix the cause, or add this "
        f"file's path to {_ALLOWLIST_PATH.name} with a reason."
    )
