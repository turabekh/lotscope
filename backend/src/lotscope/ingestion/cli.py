import asyncio
import sys
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.core.config import Settings, get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.logging import configure_logging, get_logger
from lotscope.ingestion.jobs import INGEST_JOBS, datasets_for_market

_logger = get_logger("ingestion.cli")


async def run_targets(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    market: str,
    targets: Sequence[str],
) -> list[str]:
    failures: list[str] = []
    for name in targets:
        try:
            rows = await INGEST_JOBS[(market, name)](session_factory, settings)
            _logger.info("dataset_ingested", market=market, dataset=name, rows=rows)
        except Exception as exc:
            failures.append(name)
            _logger.error("dataset_failed", market=market, dataset=name, error=str(exc))
    return failures


async def run(market: str, names: Sequence[str]) -> None:
    settings = get_settings()
    configure_logging(settings)
    targets = list(names) if names else datasets_for_market(market)
    unknown = [name for name in targets if (market, name) not in INGEST_JOBS]
    if unknown:
        raise SystemExit(f"unknown datasets for market {market}: {', '.join(unknown)}")

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        failures = await run_targets(session_factory, settings, market, targets)
    finally:
        await engine.dispose()
    if failures:
        raise SystemExit(f"datasets failed: {', '.join(failures)}")


def _parse_args(argv: Sequence[str]) -> tuple[str, list[str]]:
    args = list(argv)
    market = "phl"
    if args and args[0] == "--market":
        market = args[1]
        args = args[2:]
    return market, args


def main() -> None:
    market, names = _parse_args(sys.argv[1:])
    asyncio.run(run(market, names))


if __name__ == "__main__":
    main()
