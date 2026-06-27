import asyncio
import sys
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.core.config import Settings, get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.logging import configure_logging, get_logger
from lotscope.ingestion.jobs import INGEST_JOBS

_logger = get_logger("ingestion.cli")


async def run_targets(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    targets: Sequence[str],
) -> list[str]:
    failures: list[str] = []
    for name in targets:
        try:
            rows = await INGEST_JOBS[name](session_factory, settings)
            _logger.info("dataset_ingested", dataset=name, rows=rows)
        except Exception as exc:
            failures.append(name)
            _logger.error("dataset_failed", dataset=name, error=str(exc))
    return failures


async def run(names: Sequence[str]) -> None:
    settings = get_settings()
    configure_logging(settings)
    targets = list(names) if names else list(INGEST_JOBS)
    unknown = [name for name in targets if name not in INGEST_JOBS]
    if unknown:
        raise SystemExit(f"unknown datasets: {', '.join(unknown)}")

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        failures = await run_targets(session_factory, settings, targets)
    finally:
        await engine.dispose()
    if failures:
        raise SystemExit(f"datasets failed: {', '.join(failures)}")


def main() -> None:
    asyncio.run(run(sys.argv[1:]))


if __name__ == "__main__":
    main()
