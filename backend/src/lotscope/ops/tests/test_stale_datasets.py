from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ops.service import stale_automated_datasets

pytestmark = pytest.mark.integration

_NOW = datetime(2026, 8, 16, tzinfo=UTC)


async def _record(
    session: AsyncSession, dataset: str, *, days_ago: int | None, status: str = "success"
) -> None:
    await session.execute(
        text(
            "INSERT INTO dataset_freshness "
            "(market_code, dataset, status, last_attempt_at, last_success_at) "
            "VALUES ('phl', :dataset, :status, :attempt, :success)"
        ),
        {
            "dataset": dataset,
            "status": status,
            "attempt": _NOW,
            "success": None if days_ago is None else _NOW - timedelta(days=days_ago),
        },
    )


async def test_a_daily_dataset_weeks_behind_is_reported(db_session: AsyncSession) -> None:
    await _record(db_session, "opa_properties_public", days_ago=49)
    await db_session.flush()

    stale = await stale_automated_datasets(db_session, _NOW)

    assert [item.dataset for item in stale] == ["opa_properties_public"]
    assert "49 days ago" in stale[0].reason
    assert "daily" in stale[0].reason


async def test_a_current_daily_dataset_is_not_reported(db_session: AsyncSession) -> None:
    await _record(db_session, "opa_properties_public", days_ago=0)
    await db_session.flush()

    assert await stale_automated_datasets(db_session, _NOW) == []


async def test_a_monthly_dataset_is_not_judged_against_the_daily_bar(
    db_session: AsyncSession,
) -> None:
    await _record(db_session, "fema_flood", days_ago=49)
    await _record(db_session, "vacant_indicators", days_ago=20)
    await db_session.flush()

    assert await stale_automated_datasets(db_session, _NOW) == []


async def test_a_dataset_that_never_loaded_is_reported_when_it_should_run_daily(
    db_session: AsyncSession,
) -> None:
    await _record(db_session, "permits", days_ago=None, status="failed")
    await db_session.flush()

    stale = await stale_automated_datasets(db_session, _NOW)

    assert [item.dataset for item in stale] == ["permits"]
