from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import BuyerInvite
from lotscope.accounts.security import buyer_invite_code, create_buyer_invite_token
from lotscope.buyers.derivation import REPEAT_WINDOW_MONTHS, RepeatBuyer
from lotscope.buyers.repeat import (
    MAILING_SOURCE,
    MAILING_SOURCE_URL,
    SOURCE,
    SOURCE_URL,
)
from lotscope.core.config import Settings
from lotscope.packet.compose import LI_URL, TAX_URL, ZONING_URL, LotInputs, red_flags
from lotscope.packet.schemas import PacketLot
from lotscope.reports.letter import (
    LETTER_PURCHASES,
    LetterContext,
    LetterPurchase,
    letter_filename,
    render_buyer_letter,
)

_LETTER_SOURCES: list[tuple[str, str]] = [
    ("Recorded deeds and sale prices (rtt_summary)", SOURCE_URL),
    ("Assessment, owner and mailing address (opa_properties_public)", MAILING_SOURCE_URL),
    ("Zoning districts and by-right standards (zoning_base_districts)", ZONING_URL),
    ("Licences and inspections violations (li_event)", LI_URL),
    ("Real estate tax delinquencies (tax_status)", TAX_URL),
]

_LOT_SQL = text(
    "SELECT p.parcel_number, p.address, p.is_vacant, p.lot_area_sqft, p.base_zoning_code, "
    "(SELECT count(*) FROM li_event l WHERE l.parcel_number = p.parcel_number "
    " AND l.event_type = 'violation' "
    " AND coalesce(l.case_status, l.status, '') NOT ILIKE '%closed%') AS open_violations, "
    "(SELECT max(l.event_date) FROM li_event l WHERE l.parcel_number = p.parcel_number "
    " AND l.event_type = 'violation') AS last_violation, "
    "(SELECT bool_or(coalesce(l.is_unsafe, false) "
    " OR coalesce(l.is_imminently_dangerous, false)) FROM li_event l "
    " WHERE l.parcel_number = p.parcel_number) AS unsafe, "
    "t.is_delinquent, t.total_due, t.delinquency_owner "
    "FROM parcel p LEFT JOIN tax_status t USING (parcel_number) "
    "WHERE p.parcel_number = :parcel_number"
)


async def _grade(session: AsyncSession, parcel_number: str) -> PacketLot | None:
    from lotscope.deal.service import build_deal
    from lotscope.valuation.service import value_parcel
    from lotscope.zoning.service import assess_parcel as assess_zoning

    row = (await session.execute(_LOT_SQL, {"parcel_number": parcel_number})).one_or_none()
    if row is None:
        return None

    buildability = await assess_zoning(session, parcel_number)
    valuation = await value_parcel(session, parcel_number)
    deal = await build_deal(
        session,
        parcel_number,
        base_zoning_code=row.base_zoning_code,
        market_value=None,
        buildability=buildability,
        valuation=valuation,
    )

    dimensional = None
    if buildability is not None:
        for reason in buildability.reasons:
            if "minimum" in reason:
                dimensional = reason
                break

    inputs = LotInputs(
        parcel_number=parcel_number,
        address=row.address,
        is_vacant=bool(row.is_vacant),
        lot_area_sqft=float(row.lot_area_sqft) if row.lot_area_sqft is not None else None,
        zoning_code=row.base_zoning_code,
        open_violation_count=int(row.open_violations or 0),
        most_recent_violation=row.last_violation,
        has_unsafe_structure=bool(row.unsafe),
        is_delinquent=bool(row.is_delinquent),
        total_due=float(row.total_due) if row.total_due is not None else None,
        delinquency_owner=row.delinquency_owner,
    )

    return PacketLot(
        parcel_number=parcel_number,
        address=row.address,
        is_scheduled=False,
        is_vacant=bool(row.is_vacant),
        lot_area_sqft=inputs.lot_area_sqft,
        zoning_code=row.base_zoning_code,
        can_build_by_right=buildability.can_build_by_right if buildability else None,
        by_right_units=buildability.by_right_units if buildability else None,
        dimensional_reason=dimensional,
        provision_id=buildability.cited_section if buildability else None,
        max_allowable_offer=deal.max_allowable_offer if deal else None,
        est_margin=deal.margin if deal else None,
        red_flags=red_flags(inputs),
        verdict="LOOK",
        verdict_reason="",
        graded_as="build",
        grade_rule="build",
        computed_at=datetime.now(UTC),
    )


async def build_letter(
    session: AsyncSession,
    settings: Settings,
    buyer: RepeatBuyer,
    *,
    out_dir: Path,
    window_months: int = REPEAT_WINDOW_MONTHS,
    email: str | None = None,
) -> Path:
    purchases: list[LetterPurchase] = []
    for purchase in buyer.purchases[:LETTER_PURCHASES]:
        purchases.append(
            LetterPurchase(
                parcel_number=purchase.parcel_number,
                address=purchase.address,
                sale_date=purchase.sale_date,
                sale_price=purchase.sale_price,
                lot=await _grade(session, purchase.parcel_number),
            )
        )

    base = settings.app_base_url.rstrip("/")
    invite_url = None
    invite_code = None
    if email:
        token = create_buyer_invite_token(
            settings, buyer_key=buyer.buyer_key, display_name=buyer.display_name
        )
        invite_url = f"{base}/register?invite={token}"
    else:
        invite_code = buyer_invite_code(settings, buyer.buyer_key)

    context = LetterContext(
        buyer=buyer,
        purchases=purchases,
        window_months=window_months,
        register_url=f"{base}/register",
        invite_url=invite_url,
        invite_code=invite_code,
        generated_at=datetime.now(UTC),
        sources=_LETTER_SOURCES,
    )

    if invite_code is not None:
        await _record_invite(session, buyer, invite_code)

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / letter_filename(buyer.buyer_key)
    path.write_bytes(render_buyer_letter(context))
    return path


async def _record_invite(session: AsyncSession, buyer: RepeatBuyer, code: str) -> None:
    existing = await session.get(BuyerInvite, buyer.buyer_key)
    if existing is not None:
        existing.code = code
        existing.display_name = buyer.display_name
        return
    session.add(BuyerInvite(buyer_key=buyer.buyer_key, code=code, display_name=buyer.display_name))
    await session.flush()


def source_labels() -> list[str]:
    return [SOURCE, MAILING_SOURCE]
