import asyncio
import sys

from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.logging import configure_logging
from lotscope.ingestion.carto import CartoClient
from lotscope.ops.reconcile import DEFAULT_SAMPLE, reconcile_against_opa


async def _run(sample: int) -> int:
    settings = get_settings()
    configure_logging(settings)
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session, CartoClient(settings) as carto:
            report = await reconcile_against_opa(session, carto, sample=sample)
    finally:
        await engine.dispose()

    print(f"sampled {report.sampled}, compared {report.compared}")
    print(f"agreement {report.agreement:.1%}")
    if report.absent_upstream:
        print(f"absent upstream: {len(report.absent_upstream)}")
        for key in report.absent_upstream[:10]:
            print(f"  {key}")
    for drift in report.drifted[:40]:
        print(
            f"  {drift.parcel_number:<18}{drift.field:<20}{drift.stored!s:<28}-> {drift.upstream}"
        )
    if not report.drifted and not report.absent_upstream:
        print("no drift")
    return 1 if report.drifted or report.absent_upstream else 0


def main() -> None:
    sample = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SAMPLE
    raise SystemExit(asyncio.run(_run(sample)))


if __name__ == "__main__":
    main()
