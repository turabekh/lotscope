import argparse
import asyncio
import sys

from lotscope.ai.embeddings import VoyageEmbedder
from lotscope.ai.phillycode import DEFAULT_BATCH_CHARS, DerivationRunReport, derive_corpus
from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.errors import ConfigurationError
from lotscope.core.logging import configure_logging


def render(report: DerivationRunReport) -> str:
    lines = [
        f"Philadelphia Code derivation — source {report.source} "
        f"({report.derivation_version}, corpus {report.source_version or 'unknown'})",
        f"  documents:  {report.documents}",
        f"  provisions: {report.provisions_seen} seen, "
        f"{'all accounted for' if report.reconciled else 'RECONCILIATION FAILED'}",
        f"  {report.table_documents} table nodes embedded as linearised rows",
    ]
    for result in report.results:
        pruned = f", {result.pruned} pruned" if result.pruned else ""
        skipped = (
            result.skipped_figures
            + result.skipped_notes
            + result.skipped_containers
            + result.skipped_continuations
        )
        lines.append(
            f"  title {result.title_number}: {result.documents} documents"
            f" (folded {result.folded_leaves}, tables {result.table_documents},"
            f" skipped {skipped})"
            f"{pruned}"
        )
    return "\n".join(lines)


async def _run(titles: list[str] | None, max_batch_chars: int, pace_seconds: float) -> int:
    settings = get_settings()
    configure_logging(settings)
    if not settings.voyage_api_key:
        raise ConfigurationError("VOYAGE_API_KEY is not set; derivation needs the embedder.")
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        async with VoyageEmbedder(settings) as embedder, factory() as session:
            report = await derive_corpus(
                session,
                embedder,
                titles=titles,
                max_batch_chars=max_batch_chars,
                pace_seconds=pace_seconds,
            )
            await session.commit()
    finally:
        await engine.dispose()
    print(render(report))
    return 0 if report.reconciled else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lotscope.ai.phillycode_cli")
    parser.add_argument("--title", action="append", dest="titles")
    parser.add_argument("--max-batch-chars", type=int, default=DEFAULT_BATCH_CHARS)
    parser.add_argument("--pace-seconds", type=float, default=0.0)
    arguments = parser.parse_args(argv)
    try:
        return asyncio.run(
            _run(arguments.titles, arguments.max_batch_chars, arguments.pace_seconds)
        )
    except ConfigurationError as error:
        print(f"Derivation failed: {error.message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
