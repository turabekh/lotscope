from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.checklist.logic import build_checklist
from lotscope.checklist.schemas import ParcelChecklist
from lotscope.verdict.service import get_or_compute_current_verdict


async def build_parcel_checklist(
    session: AsyncSession, parcel_number: str
) -> ParcelChecklist | None:
    verdict = await get_or_compute_current_verdict(session, parcel_number)
    if verdict is None:
        return None
    await session.commit()
    items, summary = build_checklist(verdict)
    return ParcelChecklist(
        parcel_number=parcel_number,
        items=items,
        summary=summary,
        computed_at=datetime.now(UTC),
    )
