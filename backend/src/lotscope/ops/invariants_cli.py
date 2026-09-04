import asyncio

from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.logging import configure_logging, get_logger
from lotscope.core.market import MARKET_CODE
from lotscope.ops.invariants import breaches, check_invariants


async def _run(market: str) -> int:
    settings = get_settings()
    configure_logging(settings)
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    logger = get_logger("ops.invariants")
    try:
        async with session_factory() as session:
            results = await check_invariants(session, market)
    finally:
        await engine.dispose()

    for result in results:
        state = "BREACH" if result.breached else "ok"
        print(f"{state:>6}  {result.invariant.name:<42} {result.violations:>8,} violation(s)")
        if result.breached:
            print(f"        {result.invariant.claim}")

    failed = breaches(results)
    logger.info("invariants_checked", market=market, checked=len(results), breached=len(failed))
    return 1 if failed else 0


def main() -> None:
    market = MARKET_CODE
    raise SystemExit(asyncio.run(_run(market)))


if __name__ == "__main__":
    main()
