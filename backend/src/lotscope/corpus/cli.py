import asyncio
import logging
import time
from argparse import ArgumentParser, Namespace
from pathlib import Path

from lotscope.ai.embeddings import VoyageEmbedder
from lotscope.ai.phillycode import derive_corpus
from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.logging import configure_logging, get_logger
from lotscope.core.market import MARKET_CODE
from lotscope.corpus.service import (
    MINIMUM_COVERAGE_PCT,
    MINIMUM_PROVISIONS,
    corpus_health,
)
from lotscope.provisions.loader import (
    DEFAULT_ARTIFACT_DIR,
    ProvisionLoadError,
    load_provisions,
    read_provisions,
    read_qa_summary,
)

_NOISY_LOGGERS = ("alembic",)


def _quiet_third_party_chatter() -> None:
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def _render_coverage(rows: list[tuple[str, int, int, int, int]]) -> None:
    header = (
        f"\n{'title':>8} {'provisions':>11} {'represented':>12} "
        f"{'documents':>10} {'embedded':>9} {'embedded %':>11}"
    )
    print(header)
    print("-" * 66)
    for title_number, provisions, represented, documents, embedded in rows:
        pct = 100.0 * embedded / documents if documents else 0.0
        print(
            f"{title_number:>8} {provisions:>11,} {represented:>12,} "
            f"{documents:>10,} {embedded:>9,} {pct:>10.2f}%"
        )
    provisions_total = sum(row[1] for row in rows)
    represented_total = sum(row[2] for row in rows)
    documents_total = sum(row[3] for row in rows)
    embedded_total = sum(row[4] for row in rows)
    pct = 100.0 * embedded_total / documents_total if documents_total else 0.0
    print("-" * 66)
    print(
        f"{'TOTAL':>8} {provisions_total:>11,} {represented_total:>12,} "
        f"{documents_total:>10,} {embedded_total:>9,} {pct:>10.2f}%"
    )


async def _dry_run(directory: Path) -> int:
    try:
        summary = read_qa_summary(directory)
    except ProvisionLoadError as error:
        print(f"artifacts at {directory} are not loadable: {error}")
        return 1

    rows: list[tuple[str, int, int, int, int]] = []
    for title_number in summary.title_numbers():
        try:
            provisions = read_provisions(directory, title_number)
        except ProvisionLoadError as error:
            print(f"title {title_number}: {error}")
            return 1
        rows.append((title_number, len(provisions), 0, 0, 0))

    print(f"Artifacts at {directory} — validated, nothing written")
    _render_coverage(rows)
    total = sum(row[1] for row in rows)
    if total < MINIMUM_PROVISIONS:
        print(f"\nWARNING: {total:,} provisions is below the {MINIMUM_PROVISIONS:,} health floor")
    return 0


async def _load(directory: Path) -> int:
    settings = get_settings()
    configure_logging(settings)
    _quiet_third_party_chatter()
    logger = get_logger("corpus.load")

    if not settings.voyage_api_key:
        print("VOYAGE_API_KEY is not set; embeddings cannot be built.")
        return 1

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    started = time.monotonic()
    try:
        async with session_factory() as session:
            report = await load_provisions(session, directory, market_code=MARKET_CODE)
            await session.commit()
            print(
                f"Provisions: {report.total_provisions:,} across "
                f"{len(report.loaded_titles)} titles "
                f"(source version {report.source_version or 'unknown'})"
            )

            async with VoyageEmbedder(settings) as embedder:
                derivation = await derive_corpus(session, embedder, market_code=MARKET_CODE)

            failed = [result for result in derivation.results if result.error]
            embedded = sum(result.embedded for result in derivation.results)
            reused = sum(result.reused for result in derivation.results)
            print(
                f"Documents: {embedded:,} embedded, {reused:,} reused unchanged, "
                f"{len(failed)} title(s) failed"
            )
            for result in failed:
                print(f"  title {result.title_number}: {result.error}")

            health = await corpus_health(session, market_code=MARKET_CODE)
            _render_coverage(
                [
                    (t.title_number, t.provisions, t.represented, t.documents, t.embedded)
                    for t in health.titles
                ]
            )
    finally:
        await engine.dispose()

    elapsed = time.monotonic() - started
    print(f"\nWall time: {elapsed:.1f}s")
    logger.info(
        "corpus_loaded",
        provisions=health.total_provisions,
        documents=health.total_documents,
        embedded=health.total_embedded,
        coverage_pct=round(health.coverage_pct, 2),
        seconds=round(elapsed, 1),
    )
    if not health.healthy:
        print(
            f"INCOMPLETE: {health.total_provisions:,} provisions "
            f"(floor {MINIMUM_PROVISIONS:,}), coverage {health.coverage_pct:.2f}% "
            f"(floor {MINIMUM_COVERAGE_PCT}%). Re-run to continue; unchanged titles are skipped."
        )
        return 1
    return 0


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(prog="lotscope corpus")
    sub = parser.add_subparsers(dest="command", required=True)
    load = sub.add_parser("load", help="Load the Philadelphia Code corpus and embed it.")
    load.add_argument("--path", type=Path, default=DEFAULT_ARTIFACT_DIR)
    load.add_argument(
        "--dry-run", action="store_true", help="Validate the artifacts, write nothing."
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args: Namespace = build_parser().parse_args(argv)
    if args.dry_run:
        raise SystemExit(asyncio.run(_dry_run(args.path)))
    raise SystemExit(asyncio.run(_load(args.path)))


if __name__ == "__main__":
    main()
