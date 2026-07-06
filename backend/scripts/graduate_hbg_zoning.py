import asyncio
import sys

from sqlalchemy import text

from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.logging import configure_logging, get_logger
from lotscope.verdict.jobs import recompute_all_verdicts

PROVISIONAL = "hbg-provisional-2026"
VERIFIED = "hbg-2026-verified"


async def _run() -> None:
    settings = get_settings()
    configure_logging(settings)
    logger = get_logger("zoning.graduate")
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session:
            result = await session.execute(
                text(
                    "UPDATE zoning_standard SET code_version = :verified, updated_at = now() "
                    "WHERE market_code = 'hbg' AND code_version = :provisional"
                ),
                {"verified": VERIFIED, "provisional": PROVISIONAL},
            )
            await session.commit()
            logger.info("hbg_standards_verified", rows=result.rowcount)  # type: ignore[attr-defined]
        recomputed = await recompute_all_verdicts(session_factory, market="hbg")
        logger.info("hbg_recomputed", verdicts=recomputed)
    finally:
        await engine.dispose()


def main() -> None:
    if "--confirm" not in sys.argv[1:]:
        raise SystemExit(
            "Refusing to lift the Harrisburg provisional cap without --confirm. "
            "Run only after the reviewer sign-off is recorded (ADR-0054 addendum). "
            "Then also bump HBG_CODE_VERSION in zoning/seed_hbg.py to 'hbg-2026-verified'."
        )
    asyncio.run(_run())


if __name__ == "__main__":
    main()
