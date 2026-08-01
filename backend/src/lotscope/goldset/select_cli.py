import asyncio
import json
import sys
from pathlib import Path

from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.logging import configure_logging
from lotscope.core.markets import market_argument, market_code
from lotscope.goldset.selection import SELECTORS, select_gold_set

DEFAULT_PATH = Path("data/goldset/phl.jsonl")
DEFAULT_PER_CATEGORY = 10
_TARGET_CASES = 100


def _per_category(argv: list[str]) -> int:
    if "--per-category" not in argv:
        return DEFAULT_PER_CATEGORY
    return int(argv[argv.index("--per-category") + 1])


def _output_path(argv: list[str]) -> Path:
    if "--out" not in argv:
        return DEFAULT_PATH
    return Path(argv[argv.index("--out") + 1])


async def _run(path: Path, market: str, per_category: int) -> int:
    settings = get_settings()
    configure_logging(settings)
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            cases, found = await select_gold_set(session, market=market, per_category=per_category)
    finally:
        await engine.dispose()

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        for case in cases:
            handle.write(json.dumps(case.model_dump(mode="json")) + "\n")

    empty = [selector.category for selector in SELECTORS if found.get(selector.category, 0) == 0]
    print(f"Selected {len(cases)} parcels into {path}")
    print(f"  categories covered: {len(found) - len(empty)}/{len(SELECTORS)}")
    for selector in SELECTORS:
        print(f"    {selector.category}: {found.get(selector.category, 0)}")
    if empty:
        print(f"  NO CANDIDATES FOUND for: {', '.join(empty)}")
    if len(cases) < _TARGET_CASES:
        print(
            f"  BELOW TARGET: {len(cases)} of {_TARGET_CASES} required by LR-Q001; "
            "raise --per-category or widen the predicates."
        )
    print("  Every case is written with no expected facts. A reviewer must supply them from")
    print("  LR-Q002 sources; until then `make gold-set` compares nothing for these parcels.")
    return 0 if len(cases) >= _TARGET_CASES and not empty else 1


def main() -> None:
    argv = sys.argv[1:]
    market = market_code(market_argument(argv) or "phl")
    sys.exit(asyncio.run(_run(_output_path(argv), market, _per_category(argv))))


if __name__ == "__main__":
    main()
