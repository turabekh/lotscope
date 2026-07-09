from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.errors import NotFoundError, QuotaExceededError
from lotscope.distress.schemas import MailRecipient, build_mail_recipients
from lotscope.savedsearch.matching import (
    build_match_export_sql,
    build_match_sql,
    new_match_numbers,
)
from lotscope.savedsearch.models import SavedSearch, SavedSearchMatch
from lotscope.savedsearch.schemas import (
    SavedSearchAlert,
    SavedSearchCreate,
    SavedSearchDetail,
    SavedSearchItem,
    SavedSearchMatchItem,
    SavedSearchUpdate,
    SearchCriteria,
)

MAX_MATCHES_PER_SEARCH = 500

SAVED_SEARCH_EXPORT_HEADER: list[str] = [
    "parcel_number",
    "address",
    "owner",
    "mailing_address",
    "zip_code",
    "zoning",
    "vacant",
    "assessed_value",
    "opportunity_score",
]

_DETAIL_MATCH_SQL = text(
    "SELECT m.parcel_number, m.first_seen_at, m.notified, "
    "p.address, p.owner, "
    "coalesce(nullif(p.base_zoning_code, ''), p.resolved_zoning_code) AS base_zoning_code, "
    "p.is_vacant, p.market_value, "
    "round(pv.opportunity_score)::int AS opportunity_score "
    "FROM saved_search_match m "
    "JOIN parcel p ON p.parcel_number = m.parcel_number "
    "LEFT JOIN parcel_verdict pv ON pv.parcel_number = m.parcel_number "
    "WHERE m.saved_search_id = :search_id "
    "ORDER BY m.notified ASC, pv.opportunity_score DESC NULLS LAST, m.parcel_number"
)


def _criteria(search: SavedSearch) -> SearchCriteria:
    return SearchCriteria.model_validate(search.criteria)


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def _yes_no(value: Any) -> str:
    if value is None:
        return ""
    return "Yes" if value else "No"


def _match_item(row: Row[Any]) -> SavedSearchMatchItem:
    return SavedSearchMatchItem(
        parcel_number=row.parcel_number,
        address=row.address,
        owner=row.owner,
        base_zoning_code=row.base_zoning_code,
        is_vacant=row.is_vacant,
        market_value=_as_float(row.market_value),
        opportunity_score=row.opportunity_score,
        first_seen_at=row.first_seen_at,
        is_new=not bool(row.notified),
    )


async def count_searches(session: AsyncSession, user_id: int) -> int:
    total = await session.scalar(
        select(func.count()).select_from(SavedSearch).where(SavedSearch.user_id == user_id)
    )
    return int(total or 0)


async def _existing_match_numbers(session: AsyncSession, search_id: int) -> set[str]:
    rows = (
        await session.execute(
            select(SavedSearchMatch.parcel_number).where(
                SavedSearchMatch.saved_search_id == search_id
            )
        )
    ).all()
    return {row.parcel_number for row in rows}


async def run_match(session: AsyncSession, search: SavedSearch, *, baseline: bool) -> list[str]:
    sql, params = build_match_sql(_criteria(search), market_code=search.market_code)
    rows = (
        await session.execute(text(sql), {**params, "match_limit": MAX_MATCHES_PER_SEARCH})
    ).all()
    current = [row.parcel_number for row in rows]
    seen = await _existing_match_numbers(session, search.id)
    new_numbers = new_match_numbers(current, seen)
    if new_numbers:
        statement = insert(SavedSearchMatch).values(
            [
                {
                    "saved_search_id": search.id,
                    "parcel_number": number,
                    "notified": baseline,
                }
                for number in new_numbers
            ]
        )
        await session.execute(statement.on_conflict_do_nothing())
    search.last_run_at = datetime.now(UTC)
    await session.flush()
    return new_numbers


async def create_search(
    session: AsyncSession, user_id: int, data: SavedSearchCreate, *, limit: int | None
) -> SavedSearch:
    if limit is not None and await count_searches(session, user_id) >= limit:
        raise QuotaExceededError(
            f"Your plan can save up to {limit} searches. Remove one or upgrade to save more."
        )
    search = SavedSearch(
        user_id=user_id,
        name=data.name,
        criteria=data.criteria.model_dump(),
        alerts_enabled=data.alerts_enabled,
    )
    session.add(search)
    await session.flush()
    await run_match(session, search, baseline=True)
    return search


async def _get_owned(session: AsyncSession, user_id: int, search_id: int) -> SavedSearch:
    search = await session.get(SavedSearch, search_id)
    if search is None or search.user_id != user_id:
        raise NotFoundError(f"Saved search {search_id} was not found.")
    return search


async def update_search(
    session: AsyncSession, user_id: int, search_id: int, data: SavedSearchUpdate
) -> SavedSearch:
    search = await _get_owned(session, user_id, search_id)
    if data.name is not None:
        search.name = data.name
    if data.alerts_enabled is not None:
        search.alerts_enabled = data.alerts_enabled
    if data.criteria is not None:
        search.criteria = data.criteria.model_dump()
        await session.execute(
            delete(SavedSearchMatch).where(SavedSearchMatch.saved_search_id == search_id)
        )
        await session.flush()
        await run_match(session, search, baseline=True)
    await session.flush()
    return search


async def delete_search(session: AsyncSession, user_id: int, search_id: int) -> bool:
    search = await session.get(SavedSearch, search_id)
    if search is None or search.user_id != user_id:
        return False
    await session.delete(search)
    await session.flush()
    return True


async def _counts(session: AsyncSession, search_id: int) -> tuple[int, int]:
    match_count = await session.scalar(
        select(func.count())
        .select_from(SavedSearchMatch)
        .where(SavedSearchMatch.saved_search_id == search_id)
    )
    new_count = await session.scalar(
        select(func.count())
        .select_from(SavedSearchMatch)
        .where(
            SavedSearchMatch.saved_search_id == search_id,
            SavedSearchMatch.notified.is_(False),
        )
    )
    return int(match_count or 0), int(new_count or 0)


def _item(search: SavedSearch, match_count: int, new_count: int) -> SavedSearchItem:
    return SavedSearchItem(
        id=search.id,
        name=search.name,
        criteria=_criteria(search),
        alerts_enabled=search.alerts_enabled,
        created_at=search.created_at,
        last_run_at=search.last_run_at,
        match_count=match_count,
        new_count=new_count,
    )


async def list_searches(session: AsyncSession, user_id: int) -> list[SavedSearchItem]:
    searches = list(
        (
            await session.execute(
                select(SavedSearch)
                .where(SavedSearch.user_id == user_id)
                .order_by(SavedSearch.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    items: list[SavedSearchItem] = []
    for search in searches:
        match_count, new_count = await _counts(session, search.id)
        items.append(_item(search, match_count, new_count))
    return items


async def get_search(session: AsyncSession, user_id: int, search_id: int) -> SavedSearchDetail:
    search = await _get_owned(session, user_id, search_id)
    rows = (await session.execute(_DETAIL_MATCH_SQL, {"search_id": search_id})).all()
    matches = [_match_item(row) for row in rows]
    new_count = sum(1 for match in matches if match.is_new)
    base = _item(search, len(matches), new_count)
    return SavedSearchDetail(**base.model_dump(), matches=matches)


async def criteria_for(session: AsyncSession, user_id: int, search_id: int) -> SearchCriteria:
    return _criteria(await _get_owned(session, user_id, search_id))


async def export_search_matches(
    session: AsyncSession, user_id: int, search_id: int, *, row_limit: int
) -> list[tuple[Any, ...]]:
    search = await _get_owned(session, user_id, search_id)
    if row_limit <= 0:
        return []
    sql, params = build_match_export_sql(_criteria(search), market_code=search.market_code)
    params["match_limit"] = row_limit
    rows = (await session.execute(text(sql), params)).all()
    return [
        (
            row.parcel_number,
            row.address,
            row.owner,
            row.mailing_address,
            row.zip_code,
            row.base_zoning_code,
            _yes_no(row.is_vacant),
            _as_float(row.market_value),
            row.opportunity_score,
        )
        for row in rows
    ]


async def list_mail_recipients(
    session: AsyncSession,
    user_id: int,
    search_id: int,
    *,
    row_limit: int,
    one_per_owner: bool = False,
) -> list[MailRecipient]:
    search = await _get_owned(session, user_id, search_id)
    if row_limit <= 0:
        return []
    sql, params = build_match_export_sql(_criteria(search), market_code=search.market_code)
    params["match_limit"] = row_limit
    rows = (await session.execute(text(sql), params)).all()
    return build_mail_recipients(rows, one_per_owner=one_per_owner)


async def refresh_search(session: AsyncSession, user_id: int, search_id: int) -> SavedSearchDetail:
    search = await _get_owned(session, user_id, search_id)
    await run_match(session, search, baseline=False)
    return await get_search(session, user_id, search_id)


async def alerting_user_ids(session: AsyncSession) -> list[int]:
    rows = (
        await session.execute(
            select(SavedSearch.user_id).where(SavedSearch.alerts_enabled.is_(True)).distinct()
        )
    ).all()
    return [row.user_id for row in rows]


async def run_user_matches(session: AsyncSession, user_id: int) -> None:
    searches = list(
        (
            await session.execute(
                select(SavedSearch).where(
                    SavedSearch.user_id == user_id,
                    SavedSearch.alerts_enabled.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    for search in searches:
        await run_match(session, search, baseline=False)


async def pending_alerts_for_user(session: AsyncSession, user_id: int) -> list[SavedSearchAlert]:
    searches = list(
        (
            await session.execute(
                select(SavedSearch).where(
                    SavedSearch.user_id == user_id,
                    SavedSearch.alerts_enabled.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    alerts: list[SavedSearchAlert] = []
    for search in searches:
        rows = (await session.execute(_DETAIL_MATCH_SQL, {"search_id": search.id})).all()
        new_matches = [_match_item(row) for row in rows if not bool(row.notified)]
        if new_matches:
            alerts.append(
                SavedSearchAlert(search_id=search.id, name=search.name, new_matches=new_matches)
            )
    return alerts


async def mark_user_notified(session: AsyncSession, user_id: int) -> None:
    await session.execute(
        update(SavedSearchMatch)
        .where(
            SavedSearchMatch.notified.is_(False),
            SavedSearchMatch.saved_search_id.in_(
                select(SavedSearch.id).where(SavedSearch.user_id == user_id)
            ),
        )
        .values(notified=True)
    )
    await session.flush()
