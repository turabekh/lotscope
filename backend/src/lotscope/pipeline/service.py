from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.errors import NotFoundError, QuotaExceededError
from lotscope.pipeline.models import Deal, DealActivity
from lotscope.pipeline.schemas import DealActivityItem, DealCreate, DealItem, DealUpdate

_PARCEL_EXISTS_SQL = text("SELECT 1 FROM parcel WHERE parcel_number = :parcel_number")

_DEAL_COLUMNS = (
    "d.id, d.parcel_number, d.stage, d.note, d.target_price, d.updated_at, "
    "d.next_action, d.next_action_due, d.stage_entered_at, "
    "d.contact_name, d.contact_phone, d.contact_email, "
    "p.address, "
    "coalesce(nullif(p.base_zoning_code, ''), p.resolved_zoning_code) AS base_zoning_code, "
    "p.is_vacant, p.market_value, "
    "round(pv.opportunity_score)::int AS opportunity_score, "
    "pv.max_allowable_offer, pv.arv, pv.est_profit, pv.est_margin, pv.is_underpriced "
    "FROM deal d "
    "JOIN parcel p ON p.parcel_number = d.parcel_number "
    "LEFT JOIN parcel_verdict pv ON pv.parcel_number = d.parcel_number "
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


def _item(row: Row[Any]) -> DealItem:
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
        opportunity_score=row.opportunity_score,
        max_allowable_offer=_as_float(row.max_allowable_offer),
        arv=_as_float(row.arv),
        est_profit=_as_float(row.est_profit),
        est_margin=_as_float(row.est_margin),
        is_underpriced=row.is_underpriced,
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


async def remove_deal(session: AsyncSession, user_id: int, parcel_number: str) -> bool:
    deal = await _deal_for(session, user_id, parcel_number)
    if deal is None:
        return False
    await session.delete(deal)
    await session.flush()
    return True


async def get_deal(session: AsyncSession, user_id: int, parcel_number: str) -> DealItem | None:
    deal = await _deal_for(session, user_id, parcel_number)
    if deal is None:
        return None
    rows = (await session.execute(_LIST_SQL, {"user_id": user_id})).all()
    for row in rows:
        if row.parcel_number == parcel_number:
            return _item(row)
    return None


async def list_deals(session: AsyncSession, user_id: int) -> list[DealItem]:
    rows = (await session.execute(_LIST_SQL, {"user_id": user_id})).all()
    return [_item(row) for row in rows]


async def deals_due(session: AsyncSession, user_id: int, today: date) -> list[DealItem]:
    rows = (await session.execute(_TODAY_SQL, {"user_id": user_id, "today": today})).all()
    return [_item(row) for row in rows]


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
