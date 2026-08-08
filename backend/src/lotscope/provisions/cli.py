import argparse
import asyncio
import sys
from pathlib import Path

from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.logging import configure_logging
from lotscope.provisions.loader import (
    DEFAULT_ARTIFACT_DIR,
    PHILADELPHIA_MARKET_CODE,
    ProvisionLoadError,
    load_provisions,
)
from lotscope.provisions.schemas import LoadReport


def render(report: LoadReport) -> str:
    lines = [
        f"Philadelphia Code — source version {report.source_version or 'unknown'}",
        f"  market: {report.market_code}",
        f"  titles: {len(report.loaded_titles)} loaded, "
        f"{len(report.excluded_titles)} excluded, {report.titles_expected} accounted for",
        f"  provisions: {report.total_provisions}",
    ]
    for result in report.results:
        if result.loaded:
            pruned = f", {result.pruned_count} pruned" if result.pruned_count else ""
            lines.append(
                f"  title {result.title_number}: loaded {result.provision_count} provisions{pruned}"
            )
        else:
            lines.append(
                f"  title {result.title_number}: EXCLUDED — gate {result.excluded_gate} failed: "
                f"{result.excluded_value} ({result.excluded_detail})"
            )
    return "\n".join(lines)


async def _run(directory: Path, title_numbers: list[str] | None, market_code: str) -> int:
    settings = get_settings()
    configure_logging(settings)
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            report = await load_provisions(
                session,
                directory,
                market_code=market_code,
                title_numbers=title_numbers,
            )
            await session.commit()
    except ProvisionLoadError as error:
        print(f"Load failed: {error.message}", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()
    print(render(report))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lotscope.provisions.cli")
    parser.add_argument("--dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--title", action="append", dest="titles")
    parser.add_argument("--market", default=PHILADELPHIA_MARKET_CODE)
    arguments = parser.parse_args(argv)
    return asyncio.run(_run(arguments.dir, arguments.titles, arguments.market))


if __name__ == "__main__":
    raise SystemExit(main())
