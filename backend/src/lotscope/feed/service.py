import json
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.feed.schemas import FeedEvent, FeedResponse, FeedSummaryItem
from lotscope.ingestion.events import event_label
from lotscope.savedsearch.matching import build_where
from lotscope.savedsearch.schemas import SearchCriteria

_FROM = (
    "FROM parcel_event pe "
    "JOIN parcel p ON p.parcel_number = pe.parcel_number "
    "LEFT JOIN parcel_verdict pv ON pv.parcel_number = p.parcel_number "
    "LEFT JOIN parcel_distress pd ON pd.parcel_number = p.parcel_number "
    "LEFT JOIN tax_status ts ON ts.parcel_number = p.parcel_number"
)


def _as_json(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, str):
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else None
    return value if isinstance(value, dict) else None


async def get_feed(
    session: AsyncSession,
    *,
    criteria: SearchCriteria,
    since: datetime,
    limit: int,
) -> FeedResponse:
    where, params = build_where(criteria)
    params["since"] = since

    summary_rows = (
        await session.execute(
            text(
                f"SELECT pe.code, count(*) AS n {_FROM} "
                f"WHERE {where} AND pe.detected_at >= :since GROUP BY pe.code"
            ),
            params,
        )
    ).all()
    total = sum(row.n for row in summary_rows)
    summary = [
        FeedSummaryItem(code=row.code, label=event_label(row.code), count=row.n)
        for row in sorted(summary_rows, key=lambda r: r.n, reverse=True)
    ]

    params["limit"] = limit
    event_rows = (
        await session.execute(
            text(
                "SELECT pe.parcel_number, p.address, pe.code, pe.severity, pe.detected_at, "
                "pe.old_value, pe.new_value, round(pv.opportunity_score)::int AS opportunity_score "
                f"{_FROM} WHERE {where} AND pe.detected_at >= :since "
                "ORDER BY pe.detected_at DESC, pe.id DESC LIMIT :limit"
            ),
            params,
        )
    ).all()
    events = [
        FeedEvent(
            parcel_number=row.parcel_number,
            address=row.address,
            code=row.code,
            label=event_label(row.code),
            severity=row.severity,
            detected_at=row.detected_at,
            old_value=_as_json(row.old_value),
            new_value=_as_json(row.new_value),
            opportunity_score=row.opportunity_score,
        )
        for row in event_rows
    ]
    return FeedResponse(
        since=since, total=total, returned=len(events), summary=summary, events=events
    )
