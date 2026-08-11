import argparse
import asyncio
import sys

from lotscope.ai.derivation import DERIVATION_VERSION
from lotscope.ai.phillycode import PHILADELPHIA_MARKET_CODE
from lotscope.ai.verification import VerificationReport, verify_derivation
from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.logging import configure_logging


def render(report: VerificationReport) -> str:
    lines = [
        f"Philadelphia Code derivation verification — market {report.market_code}, "
        f"expected version {report.derivation_version}",
        f"  {'title':>6}  {'expected':>9}  {'actual':>8}  {'short':>7}  ledger",
    ]
    for title in report.titles:
        status = title.ledger_status or "no ledger row"
        versions = ",".join(title.document_versions) or "-"
        lines.append(
            f"  {title.title_number:>6}  {title.expected:>9}  {title.actual:>8}  "
            f"{title.shortfall:>7}  {status} ({versions})"
        )
    lines.append(f"  TOTAL expected {report.expected}, actual {report.actual}")
    if report.breached:
        names = ", ".join(title.title_number for title in report.breached)
        lines.append(f"  FAILED — ledger claims these complete but they are short: {names}")
    if report.stale_versions:
        names = ", ".join(title.title_number for title in report.stale_versions)
        lines.append(f"  FAILED — documents not at {report.derivation_version}: {names}")
    if report.require_complete:
        short = [title for title in report.titles if title.shortfall != 0]
        if short:
            names = ", ".join(title.title_number for title in short)
            lines.append(f"  FAILED — --require-complete and these are short: {names}")
    if report.unclaimed:
        names = ", ".join(title.title_number for title in report.unclaimed)
        lines.append(f"  note: no successful ledger row for: {names}")
    lines.append("  OK" if report.ok else "  NOT OK")
    return "\n".join(lines)


async def _run(market_code: str, require_complete: bool) -> int:
    settings = get_settings()
    configure_logging(settings)
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            report = await verify_derivation(
                session,
                market_code=market_code,
                derivation_version=DERIVATION_VERSION,
                require_complete=require_complete,
            )
    finally:
        await engine.dispose()
    print(render(report))
    return 0 if report.ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lotscope.ai.verify_cli")
    parser.add_argument("--market", default=PHILADELPHIA_MARKET_CODE)
    parser.add_argument("--require-complete", action="store_true")
    arguments = parser.parse_args(argv)
    return asyncio.run(_run(arguments.market, arguments.require_complete))


if __name__ == "__main__":
    sys.exit(main())
