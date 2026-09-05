from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.schemas import ParcelReportResult
from lotscope.assemblage.service import compute_assemblage
from lotscope.checklist.service import build_parcel_checklist
from lotscope.distress.service import assess_parcel_distress
from lotscope.parcels.service import get_parcel_detail
from lotscope.reports.dossier import render_dossier_pdf
from lotscope.verdict.service import get_or_compute_current_verdict
from lotscope.zoning.service import assess_parcel

_DISCLAIMER = (
    "Informational only - not legal, financial, or real-estate advice. "
    "Philadelphia city data is provided as-is. (c) LotScope PHL."
)


async def build_parcel_dossier(
    session: AsyncSession,
    parcel_number: str,
    *,
    report: ParcelReportResult | None = None,
) -> bytes | None:
    detail = await get_parcel_detail(session, parcel_number)
    if detail is None:
        return None

    verdict = await get_or_compute_current_verdict(session, parcel_number)
    await session.commit()

    assemblage = await compute_assemblage(session, parcel_number)
    distress = await assess_parcel_distress(session, parcel_number)
    checklist = await build_parcel_checklist(session, parcel_number)
    buildability = await assess_parcel(session, parcel_number)

    return render_dossier_pdf(
        detail=detail,
        verdict=verdict,
        buildability=buildability,
        assemblage=assemblage,
        distress=distress,
        checklist=checklist,
        report=report,
        generated_at=datetime.now(UTC),
        disclaimer=_DISCLAIMER,
    )
