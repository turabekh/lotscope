import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.admin.schemas import AdminUserUpdate
from lotscope.admin.service import (
    list_datasets,
    list_job_runs,
    list_users,
    platform_overview,
    update_user,
)
from lotscope.core.errors import NotFoundError

pytestmark = pytest.mark.integration


async def _seed(session: AsyncSession) -> int:
    await session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active) VALUES "
            "('a@example.com', 'x', 'user', 'free', true), "
            "('b@example.com', 'x', 'user', 'pro', true), "
            "('c@example.com', 'x', 'admin', 'enterprise', true)"
        )
    )
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, is_vacant) VALUES "
            "('000000001', true), ('000000002', false)"
        )
    )
    await session.execute(
        text(
            "INSERT INTO dataset_freshness (dataset, status, row_count) "
            "VALUES ('opa', 'success', 100), ('rtt', 'failed', 0)"
        )
    )
    await session.flush()
    user_id = await session.scalar(text("SELECT id FROM app_user WHERE email = 'a@example.com'"))
    return int(user_id)


async def test_platform_overview_counts(db_session: AsyncSession) -> None:
    await _seed(db_session)
    overview = await platform_overview(db_session)
    assert overview.users_total == 3
    assert overview.users_by_tier == {"free": 1, "pro": 1, "enterprise": 1}
    assert overview.parcels_total == 2
    assert overview.parcels_vacant == 1


async def test_list_datasets_sorted(db_session: AsyncSession) -> None:
    await _seed(db_session)
    datasets = await list_datasets(db_session)
    assert [d.dataset for d in datasets] == ["opa", "rtt"]
    assert datasets[1].status == "failed"


async def test_list_users_paginates(db_session: AsyncSession) -> None:
    await _seed(db_session)
    page = await list_users(db_session, limit=2, offset=0)
    assert page.total == 3
    assert len(page.users) == 2


async def test_update_user_changes_fields(db_session: AsyncSession) -> None:
    user_id = await _seed(db_session)
    updated = await update_user(
        db_session, user_id, AdminUserUpdate(tier="pro", role="admin", is_active=False)
    )
    assert updated.tier == "pro"
    assert updated.role == "admin"
    assert updated.is_active is False


async def test_update_user_missing_raises(db_session: AsyncSession) -> None:
    await _seed(db_session)
    with pytest.raises(NotFoundError):
        await update_user(db_session, 999999, AdminUserUpdate(tier="pro"))


async def test_a_cron_run_can_be_listed_even_though_nobody_triggered_it(
    db_session: AsyncSession,
) -> None:
    """Production 500ed on /admin/jobs/runs for exactly this: crons have no triggerer."""
    await db_session.execute(
        text(
            "INSERT INTO job_run (job_id, label, kind, status, started_at, finished_at, "
            "duration_ms, triggered_by) VALUES ('cron:ingest_all', 'ingest_all', 'cron', "
            "'success', now(), now(), 3437, NULL)"
        )
    )
    await db_session.flush()

    rows = await list_job_runs(db_session, limit=10)

    assert [row.label for row in rows] == ["ingest_all"]
    assert rows[0].triggered_by is None
    assert rows[0].duration_ms == 3437
