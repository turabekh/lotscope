import asyncio
import sys
from collections.abc import Sequence

from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.logging import configure_logging, get_logger
from lotscope.ingestion.jobs import INGEST_JOBS

_logger = get_logger("ingestion.cli")


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
        for name in targets:
            rows = await INGEST_JOBS[name](session_factory, settings)
            _logger.info("dataset_ingested", dataset=name, rows=rows)
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(run(sys.argv[1:]))


if __name__ == "__main__":
    main()
