from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.feed.service import get_feed
from lotscope.savedsearch.schemas import SearchCriteria

pytestmark = pytest.mark.integration


async def _add_parcel(session: AsyncSession, parcel_number: str, *, vacant: bool) -> None:
    await session.execute(
        text("INSERT INTO parcel (parcel_number, owner, is_vacant) VALUES (:pn, 'OWNER', :v)"),
        {"pn": parcel_number, "v": vacant},
    )


async def _add_event(
    session: AsyncSession, parcel_number: str, code: str, *, days_ago: int
) -> None:
    detected = datetime.now(UTC) - timedelta(days=days_ago)
    await session.execute(
        text(
            "INSERT INTO parcel_event (parcel_number, dataset, code, severity, detected_at) "
            "VALUES (:pn, 'tax_delinquency', :code, 'high', :detected)"
        ),
        {"pn": parcel_number, "code": code, "detected": detected},
    )


async def test_feed_summarizes_and_lists_recent_events(db_session: AsyncSession) -> None:
    await _add_parcel(db_session, "000000001", vacant=True)
    await _add_event(db_session, "000000001", "delinquent", days_ago=0)
    await _add_event(db_session, "000000001", "tax_up", days_ago=0)
    await _add_event(db_session, "000000001", "delinquent", days_ago=10)
    await db_session.flush()

    result = await get_feed(
        db_session,
        criteria=SearchCriteria(),
        since=datetime.now(UTC) - timedelta(days=1),
        limit=200,
    )
    assert result.total == 2
    counts = {item.code: item.count for item in result.summary}
    assert counts == {"delinquent": 1, "tax_up": 1}
    assert result.summary[0].label
    assert result.returned == 2


async def test_feed_filters_by_criteria(db_session: AsyncSession) -> None:
    await _add_parcel(db_session, "000000001", vacant=True)
    await _add_parcel(db_session, "000000002", vacant=False)
    await _add_event(db_session, "000000001", "delinquent", days_ago=0)
    await _add_event(db_session, "000000002", "delinquent", days_ago=0)
    await db_session.flush()

    result = await get_feed(
        db_session,
        criteria=SearchCriteria(vacant_only=True),
        since=datetime.now(UTC) - timedelta(days=1),
        limit=200,
    )
    assert result.total == 1
    assert result.events[0].parcel_number == "000000001"


async def test_feed_respects_the_since_window(db_session: AsyncSession) -> None:
    await _add_parcel(db_session, "000000001", vacant=True)
    await _add_event(db_session, "000000001", "delinquent", days_ago=10)
    await db_session.flush()

    result = await get_feed(
        db_session,
        criteria=SearchCriteria(),
        since=datetime.now(UTC) - timedelta(days=1),
        limit=200,
    )
    assert result.total == 0
    assert result.events == []
