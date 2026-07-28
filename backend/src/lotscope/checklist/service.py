from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.checklist.logic import build_checklist
from lotscope.checklist.schemas import ParcelChecklist
from lotscope.parcels.abatement import has_active_exemption
from lotscope.parcels.service import get_parcel_detail
from lotscope.verdict.service import get_or_compute_current_verdict

_TAX_KNOWN_SQL = text("SELECT is_delinquent FROM tax_status WHERE parcel_number = :parcel_number")


async def _tax_status_unknown(session: AsyncSession, parcel_number: str) -> bool:
    row = (await session.execute(_TAX_KNOWN_SQL, {"parcel_number": parcel_number})).one_or_none()
    return row is not None and row.is_delinquent is None


async def build_parcel_checklist(
    session: AsyncSession, parcel_number: str
) -> ParcelChecklist | None:
    verdict = await get_or_compute_current_verdict(session, parcel_number)
    if verdict is None:
        return None
    await session.commit()
    detail = await get_parcel_detail(session, parcel_number)
    has_abatement = detail is not None and has_active_exemption(
        detail.exempt_land, detail.exempt_building
    )
    market = parcel_number.split(":", 1)[0]
    items, summary = build_checklist(
        verdict,
        has_abatement=has_abatement,
        market_code=market,
        tax_status_unknown=await _tax_status_unknown(session, parcel_number),
    )
    return ParcelChecklist(
        parcel_number=parcel_number,
        items=items,
        summary=summary,
        computed_at=datetime.now(UTC),
    )
