import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import func, select, text
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.errors import NotFoundError, QuotaExceededError
from lotscope.pipeline.models import Deal, DealActivity
from lotscope.pipeline.schemas import (
    DealActivityItem,
    DealCreate,
    DealItem,
    DealUpdate,
    OfferRequest,
)
from lotscope.reports.loi import (
    DEFAULT_EXPIRATION_DAYS,
    LoiSigner,
    LoiTerms,
    compose_loi,
    loi_filename,
    render_loi_pdf,
)
from lotscope.valuation.schemas import ValuationResult
from lotscope.valuation.service import value_parcel
from lotscope.verdict.schemas import VerdictResult
from lotscope.verdict.service import compute_verdict, get_verdict

_PARCEL_EXISTS_SQL = text("SELECT 1 FROM parcel WHERE parcel_number = :parcel_number")

_DEAL_COLUMNS = (
    "d.id, d.parcel_number, d.stage, d.note, d.target_price, d.updated_at, "
    "d.next_action, d.next_action_due, d.stage_entered_at, "
    "d.contact_name, d.contact_phone, d.contact_email, "
    "p.address, "
    "coalesce(nullif(p.base_zoning_code, ''), p.resolved_zoning_code) AS base_zoning_code, "
    "p.is_vacant, p.market_value, "
    # The next sale this lot is actually listed for, so the table can say when it goes.
    "ss.sale_date, "
    # What the Analyst said in the run that put this row here. agent_run_id is the link;
    # without it the note would be a guess about which conversation this came from.
    "d.agent_run_id, ar.answer AS analyst_note, ar.created_at AS analyst_note_at "
    "FROM deal d "
    "JOIN parcel p ON p.parcel_number = d.parcel_number "
    "LEFT JOIN agent_run ar ON ar.id = d.agent_run_id "
    "LEFT JOIN LATERAL ("
    "  SELECT s.sale_date FROM sheriff_sale s "
    "  WHERE s.parcel_number = d.parcel_number AND s.sale_date >= current_date "
    "  ORDER BY s.sale_date LIMIT 1"
    ") ss ON TRUE "
)

_LIST_SQL = text(
    "SELECT " + _DEAL_COLUMNS + "WHERE d.user_id = :user_id ORDER BY d.updated_at DESC"
)
_TODAY_SQL = text(
    "SELECT " + _DEAL_COLUMNS + "WHERE d.user_id = :user_id AND d.next_action_due IS NOT NULL "
    "AND d.next_action_due <= :today ORDER BY d.next_action_due ASC"
)


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def _item(row: Row[Any], verdict: VerdictResult | None = None) -> DealItem:
    """One row of the pipeline.

    The economics are the verdict computed for this read, not a stored copy: these are
    the numbers a buyer bids on, and a pipeline is tens of rows, not thousands.
    """
    return DealItem(
        id=row.id,
        parcel_number=row.parcel_number,
        stage=row.stage,
        note=row.note,
        target_price=_as_float(row.target_price),
        next_action=row.next_action,
        next_action_due=row.next_action_due,
        stage_entered_at=row.stage_entered_at,
        contact_name=row.contact_name,
        contact_phone=row.contact_phone,
        contact_email=row.contact_email,
        address=row.address,
        base_zoning_code=row.base_zoning_code,
        is_vacant=row.is_vacant,
        market_value=_as_float(row.market_value),
        opportunity_score=round(verdict.opportunity_score) if verdict else None,
        max_allowable_offer=verdict.max_allowable_offer if verdict else None,
        arv=verdict.arv if verdict else None,
        est_profit=verdict.est_profit if verdict else None,
        est_margin=verdict.est_margin if verdict else None,
        is_underpriced=verdict.is_underpriced if verdict else None,
        sale_date=row.sale_date,
        agent_run_id=row.agent_run_id,
        analyst_note=(row.analyst_note or None),
        analyst_note_at=row.analyst_note_at,
        updated_at=row.updated_at,
    )


async def count_deals(session: AsyncSession, user_id: int) -> int:
    total = await session.scalar(
        select(func.count()).select_from(Deal).where(Deal.user_id == user_id)
    )
    return int(total or 0)


async def _deal_for(session: AsyncSession, user_id: int, parcel_number: str) -> Deal | None:
    deal: Deal | None = await session.scalar(
        select(Deal).where(Deal.user_id == user_id, Deal.parcel_number == parcel_number)
    )
    return deal


async def add_deal(
    session: AsyncSession, user_id: int, data: DealCreate, *, limit: int | None
) -> Deal:
    exists = await session.scalar(_PARCEL_EXISTS_SQL, {"parcel_number": data.parcel_number})
    if not exists:
        raise NotFoundError(f"Parcel {data.parcel_number} was not found.")
    deal = await _deal_for(session, user_id, data.parcel_number)
    if deal is not None:
        return deal
    if limit is not None and await count_deals(session, user_id) >= limit:
        raise QuotaExceededError(
            f"Your plan can track up to {limit} deals. Close one or upgrade to add more."
        )
    deal = Deal(
        user_id=user_id,
        parcel_number=data.parcel_number,
        stage=data.stage,
        note=data.note,
        target_price=data.target_price,
        stage_entered_at=datetime.now(UTC),
    )
    session.add(deal)
    await session.flush()
    return deal


async def update_deal(
    session: AsyncSession, user_id: int, parcel_number: str, data: DealUpdate
) -> Deal:
    deal = await _deal_for(session, user_id, parcel_number)
    if deal is None:
        raise NotFoundError(f"Parcel {parcel_number} is not in your pipeline.")
    if data.stage is not None and data.stage != deal.stage:
        session.add(
            DealActivity(
                deal_id=deal.id,
                kind="stage_change",
                from_stage=deal.stage,
                to_stage=data.stage,
            )
        )
        deal.stage = data.stage
        deal.stage_entered_at = datetime.now(UTC)
    if data.note is not None:
        deal.note = data.note
    if data.target_price is not None:
        deal.target_price = data.target_price
    if data.next_action is not None and data.next_action != deal.next_action:
        deal.next_action = data.next_action
        session.add(DealActivity(deal_id=deal.id, kind="next_action", body=data.next_action))
    if data.next_action_due is not None:
        deal.next_action_due = data.next_action_due
    if data.contact_name is not None:
        deal.contact_name = data.contact_name
    if data.contact_phone is not None:
        deal.contact_phone = data.contact_phone
    if data.contact_email is not None:
        deal.contact_email = data.contact_email
    await session.flush()
    return deal


_PARCEL_FACTS_SQL = text("SELECT address, local_key FROM parcel WHERE parcel_number = :pn")


def _comp_fingerprint(valuation: ValuationResult | None) -> str | None:
    if valuation is None or not valuation.comps:
        return None
    parts = "|".join(sorted(comp.parcel_number for comp in valuation.comps))
    raw = f"{parts}@{valuation.computed_at.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


async def generate_offer(
    session: AsyncSession,
    user_id: int,
    parcel_number: str,
    request: OfferRequest,
    *,
    default_signer: LoiSigner,
    now: datetime,
) -> tuple[bytes, str]:
    facts = (await session.execute(_PARCEL_FACTS_SQL, {"pn": parcel_number})).one_or_none()
    if facts is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    # The offer letter goes to an owner, so its number is computed here and now rather
    # than read from a cache or an index.
    verdict = await compute_verdict(session, parcel_number)
    mao = verdict.max_allowable_offer if verdict is not None else None
    valuation = await value_parcel(session, parcel_number)

    terms = LoiTerms(
        all_cash=request.all_cash,
        as_is=request.as_is,
        earnest_money=request.earnest_money,
        close_days=request.close_days,
        inspection_days=request.inspection_days,
        expiration=request.expiration or (now.date() + timedelta(days=DEFAULT_EXPIRATION_DAYS)),
    )
    signer = LoiSigner(
        entity_name=request.entity_name or default_signer.entity_name,
        signer_name=request.signer_name or default_signer.signer_name,
        signer_phone=request.signer_phone or default_signer.signer_phone,
        signer_email=request.signer_email or default_signer.signer_email,
    )
    document = compose_loi(
        parcel_number=parcel_number,
        local_key=facts.local_key,
        address=facts.address or parcel_number,
        max_allowable_offer=mao,
        offer_price_override=request.offer_price,
        terms=terms,
        signer=signer,
        has_comps=bool(valuation and valuation.comps),
        generated_at=now,
    )
    pdf = render_loi_pdf(document, valuation)

    deal = await add_deal(session, user_id, DealCreate(parcel_number=parcel_number), limit=None)
    payload = {
        "offer_price": document.offer_price,
        "mao_framing": document.mao_framing,
        "all_cash": terms.all_cash,
        "as_is": terms.as_is,
        "earnest_money": terms.earnest_money,
        "close_days": terms.close_days,
        "inspection_days": terms.inspection_days,
        "expiration": terms.expiration.isoformat() if terms.expiration else None,
        "comp_count": len(valuation.comps) if valuation else 0,
        "comp_fingerprint": _comp_fingerprint(valuation),
    }
    session.add(DealActivity(deal_id=deal.id, kind="offer_generated", body=json.dumps(payload)))
    await session.flush()
    return pdf, loi_filename(document)


async def remove_deal(session: AsyncSession, user_id: int, parcel_number: str) -> bool:
    deal = await _deal_for(session, user_id, parcel_number)
    if deal is None:
        return False
    await session.delete(deal)
    await session.flush()
    return True


async def _items(
    session: AsyncSession, rows: Sequence[Row[Any]], *, redis: Redis | None
) -> list[DealItem]:
    items = []
    for row in rows:
        verdict = await get_verdict(session, row.parcel_number, redis=redis)
        items.append(_item(row, verdict))
    return items


async def get_deal(
    session: AsyncSession, user_id: int, parcel_number: str, *, redis: Redis | None = None
) -> DealItem | None:
    deal = await _deal_for(session, user_id, parcel_number)
    if deal is None:
        return None
    rows = (await session.execute(_LIST_SQL, {"user_id": user_id})).all()
    matching = [row for row in rows if row.parcel_number == parcel_number]
    if not matching:
        return None
    return (await _items(session, matching, redis=redis))[0]


async def list_deals(
    session: AsyncSession, user_id: int, *, redis: Redis | None = None
) -> list[DealItem]:
    rows = (await session.execute(_LIST_SQL, {"user_id": user_id})).all()
    return await _items(session, rows, redis=redis)


PIPELINE_EXPORT_HEADER: list[str] = [
    "parcel_number",
    "address",
    "stage",
    "next_action",
    "next_action_due",
    "target_price",
    "opportunity_score",
    "max_allowable_offer",
    "arv",
    "est_profit",
    "est_margin",
    "is_underpriced",
    "zoning",
    "market_value",
    "vacant",
    "contact_name",
    "contact_phone",
    "contact_email",
    "updated_at",
]


async def export_deals(
    session: AsyncSession, user_id: int, *, row_limit: int, redis: Redis | None = None
) -> list[tuple[Any, ...]]:
    if row_limit <= 0:
        return []
    deals = await list_deals(session, user_id, redis=redis)
    rows: list[tuple[Any, ...]] = []
    for deal in deals[:row_limit]:
        traced = bool(deal.contact_phone or deal.contact_email)
        contact_name = deal.contact_name if traced else "not traced"
        rows.append(
            (
                deal.parcel_number,
                deal.address,
                deal.stage,
                deal.next_action,
                deal.next_action_due.isoformat() if deal.next_action_due else None,
                deal.target_price,
                deal.opportunity_score,
                deal.max_allowable_offer,
                deal.arv,
                deal.est_profit,
                deal.est_margin,
                deal.is_underpriced,
                deal.base_zoning_code,
                deal.market_value,
                deal.is_vacant,
                contact_name,
                deal.contact_phone,
                deal.contact_email,
                deal.updated_at.isoformat() if deal.updated_at else None,
            )
        )
    return rows


async def deals_due(
    session: AsyncSession, user_id: int, today: date, *, redis: Redis | None = None
) -> list[DealItem]:
    rows = (await session.execute(_TODAY_SQL, {"user_id": user_id, "today": today})).all()
    return await _items(session, rows, redis=redis)


async def list_activity(
    session: AsyncSession, user_id: int, parcel_number: str
) -> list[DealActivityItem]:
    rows = (
        await session.execute(
            select(DealActivity)
            .join(Deal, Deal.id == DealActivity.deal_id)
            .where(Deal.user_id == user_id, Deal.parcel_number == parcel_number)
            .order_by(DealActivity.created_at.desc(), DealActivity.id.desc())
        )
    ).scalars()
    return [DealActivityItem.model_validate(row, from_attributes=True) for row in rows]
