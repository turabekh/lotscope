import asyncio
import json
import sys
from pathlib import Path

from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.logging import configure_logging
from lotscope.goldset.loader import load_cases
from lotscope.goldset.schemas import EvaluationReport
from lotscope.goldset.service import evaluate_gold_set

DEFAULT_PATH = Path("data/goldset/phl.jsonl")
_CATEGORY_TOTAL = 17


def render(report: EvaluationReport) -> str:
    lines = [
        f"Gold set — verdict {report.verdict_version}",
        f"  cases: {report.total_cases}  evaluated: {report.evaluated}",
        f"  professionally reviewed: {report.reviewed_cases}/{report.total_cases}",
        f"  awaiting expected facts: {report.cases_without_expectations}/{report.total_cases}",
        f"  categories covered: {len(report.category_coverage)}/{_CATEGORY_TOTAL}",
        f"  critical: {report.critical}  material: {report.material}  minor: {report.minor}"
        + (
            "  (no expectations recorded on "
            f"{report.cases_without_expectations} case(s) - nothing was compared for them)"
            if report.cases_without_expectations
            else ""
        ),
    ]
    if report.missing_verdict:
        lines.append(f"  no verdict for: {', '.join(report.missing_verdict[:10])}")
    for item in report.discrepancies:
        lines.append(
            f"  [{item.severity}] {item.parcel_number} {item.field_name}: "
            f"expected {item.expected}, actual {item.actual}"
        )
    return "\n".join(lines)


async def _run(path: Path, as_json: bool) -> int:
    settings = get_settings()
    configure_logging(settings)
    cases = load_cases(path)
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            report = await evaluate_gold_set(session, cases)
    finally:
        await engine.dispose()

    print(json.dumps(report.model_dump(), indent=2, default=str) if as_json else render(report))
    return 1 if report.critical else 0


def main() -> None:
    args = sys.argv[1:]
    path = Path(args[0]) if args and not args[0].startswith("--") else DEFAULT_PATH
    raise SystemExit(asyncio.run(_run(path, "--json" in args)))


if __name__ == "__main__":
    main()
