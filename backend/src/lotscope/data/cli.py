import asyncio
import logging
from argparse import ArgumentParser, Namespace

from sqlalchemy import text

from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.logging import configure_logging, get_logger
from lotscope.core.market import MARKET_CODE
from lotscope.data.purge import (
    PurgeTarget,
    build_deletion_graph,
    count_targets,
    delete_targets,
    load_full_metadata,
)

_ABSENT = "absent"
_NOISY_LOGGERS = ("alembic",)


def _quiet_third_party_chatter() -> None:
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def _render(rows: list[tuple[PurgeTarget, int | None]], *, heading: str) -> None:
    print(f"\n{heading}")
    print(f"{'#':>3}  {'table':<26} {'reached by':<10} {'rows':>10}  note")
    print("-" * 96)
    for index, (target, count) in enumerate(rows, start=1):
        shown = _ABSENT if count is None else f"{count:,}"
        print(f"{index:>3}  {target.key:<26} {target.reason:<10} {shown:>10}  {target.note}")
    total = sum(c for _, c in rows if c is not None)
    parcels = next((c for t, c in rows if t.key == "parcel"), 0) or 0
    print("-" * 96)
    print(f"{'':>3}  {'TOTAL rows':<26} {'':<10} {total:>10,}")
    print(f"{'':>3}  {'parcels':<26} {'':<10} {parcels:>10,}")


async def _purge(args: Namespace) -> int:
    settings = get_settings()
    configure_logging(settings)
    _quiet_third_party_chatter()
    logger = get_logger("data.purge")
    targets = build_deletion_graph(load_full_metadata(), market_code=MARKET_CODE)

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session:
            before = await count_targets(session, targets)
            _render(before, heading=f"Rows outside market {MARKET_CODE!r} — deletion order")
            if args.dry_run:
                logger.info("purge_dry_run", tables=len(targets))
                return 0

            failing: str | None = None
            try:
                await delete_targets(session, targets)
                await session.commit()
            except Exception as error:
                await session.rollback()
                failing = getattr(error, "table", None) or str(error)
                logger.error("purge_failed", error=str(error))
                print(f"\nFAILED — rolled back. Offending statement: {failing}")
                return 1

            after = await count_targets(session, targets)
            _render(after, heading="After — same graph, recounted")
            logger.info("purge_completed", tables=len(targets))
            return 0
    finally:
        await engine.dispose()


async def _vacuum() -> int:
    settings = get_settings()
    engine = create_engine(settings)
    try:
        async with engine.connect() as connection:
            await connection.execution_options(isolation_level="AUTOCOMMIT")
            await connection.execute(text("VACUUM ANALYZE parcel"))
    finally:
        await engine.dispose()
    print("VACUUM ANALYZE parcel — done")
    return 0


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(prog="lotscope data")
    sub = parser.add_subparsers(dest="command", required=True)

    purge = sub.add_parser(
        "purge-other-markets",
        help="Delete every parcel outside Philadelphia and everything keyed to it.",
    )
    purge.add_argument("--dry-run", action="store_true", help="Show the graph, delete nothing.")
    purge.add_argument("--yes", action="store_true", help="Perform the deletion.")

    sub.add_parser("vacuum-parcel", help="VACUUM ANALYZE parcel.")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "vacuum-parcel":
        raise SystemExit(asyncio.run(_vacuum()))

    if args.dry_run == args.yes:
        parser.error("pass exactly one of --dry-run or --yes")
    raise SystemExit(asyncio.run(_purge(args)))


if __name__ == "__main__":
    main()
