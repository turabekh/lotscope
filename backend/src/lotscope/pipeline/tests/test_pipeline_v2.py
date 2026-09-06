from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.pipeline.schemas import DealCreate, DealUpdate
from lotscope.pipeline.service import (
    add_deal,
    deals_due,
    list_activity,
    list_deals,
    update_deal,
)

pytestmark = pytest.mark.integration

_TODAY = datetime.now(UTC).date()


async def _seed(session: AsyncSession) -> int:
    await session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
            "VALUES ('v2@example.com', 'x', 'user', 'pro', true)"
        )
    )
    user_id = await session.scalar(text("SELECT id FROM app_user WHERE email = 'v2@example.com'"))
    for number in ("000000001", "000000002", "000000003"):
        await session.execute(
            text("INSERT INTO parcel (parcel_number, address) VALUES (:pn, :addr)"),
            {"pn": number, "addr": f"{number} Main St"},
        )
    await session.flush()
    return int(user_id)


async def test_stage_change_stamps_time_and_logs_activity(db_session: AsyncSession) -> None:
    user_id = await _seed(db_session)
    await add_deal(db_session, user_id, DealCreate(parcel_number="000000001"), limit=None)
    await update_deal(db_session, user_id, "000000001", DealUpdate(stage="offer"))

    deal = await list_deals(db_session, user_id)
    assert deal[0].stage == "offer"
    assert deal[0].stage_entered_at is not None

    activity = await list_activity(db_session, user_id, "000000001")
    assert len(activity) == 1
    assert activity[0].kind == "stage_change"
    assert activity[0].from_stage == "lead"
    assert activity[0].to_stage == "offer"


async def test_setting_next_action_logs_activity(db_session: AsyncSession) -> None:
    user_id = await _seed(db_session)
    await add_deal(db_session, user_id, DealCreate(parcel_number="000000001"), limit=None)
    await update_deal(db_session, user_id, "000000001", DealUpdate(next_action="Call the owner"))
    activity = await list_activity(db_session, user_id, "000000001")
    assert [a.kind for a in activity] == ["next_action"]
    assert activity[0].body == "Call the owner"


async def test_deals_due_returns_overdue_and_today_only(db_session: AsyncSession) -> None:
    user_id = await _seed(db_session)
    await add_deal(db_session, user_id, DealCreate(parcel_number="000000001"), limit=None)
    await add_deal(db_session, user_id, DealCreate(parcel_number="000000002"), limit=None)
    await add_deal(db_session, user_id, DealCreate(parcel_number="000000003"), limit=None)
    await update_deal(
        db_session, user_id, "000000001", DealUpdate(next_action_due=_TODAY - timedelta(days=2))
    )
    await update_deal(db_session, user_id, "000000002", DealUpdate(next_action_due=_TODAY))
    await update_deal(
        db_session, user_id, "000000003", DealUpdate(next_action_due=_TODAY + timedelta(days=5))
    )

    due = await deals_due(db_session, user_id, _TODAY)
    assert [d.parcel_number for d in due] == ["000000001", "000000002"]


async def test_a_deal_row_carries_the_economics_computed_for_this_read(
    db_session: AsyncSession,
) -> None:
    """The pipeline shows what a lot supports now, not what a sweep last wrote."""
    from lotscope.zoning.seed import seed_zoning_standards

    user_id = await _seed(db_session)
    await seed_zoning_standards(db_session)
    await db_session.execute(
        text(
            "INSERT INTO zoning_district (code, geom_local) VALUES ('RSA-5', "
            "ST_GeomFromText('POLYGON((-100 -100,-100 100,100 100,100 -100,-100 -100))', 2272))"
        )
    )
    await db_session.execute(
        text(
            "UPDATE parcel SET lot_area_sqft = 1600, frontage_ft = 18, depth_ft = 90, "
            "market_value = 150000, base_zoning_code = 'RSA-5', is_vacant = TRUE, "
            "geom_local = ST_GeomFromText('POLYGON((0 0,0 10,10 10,10 0,0 0))', 2272) "
            "WHERE parcel_number = '000000001'"
        )
    )
    await add_deal(db_session, user_id, DealCreate(parcel_number="000000001"), limit=None)
    await db_session.flush()

    deal = (await list_deals(db_session, user_id))[0]

    assert deal.opportunity_score is not None
    # Nothing was read from a table of stored verdicts: there is not one.
    assert await db_session.scalar(text("SELECT to_regclass('parcel_verdict')::text")) is None


async def test_export_marks_untraced_deals_not_traced(db_session: AsyncSession) -> None:
    from lotscope.pipeline.service import export_deals

    user_id = await _seed(db_session)
    await add_deal(db_session, user_id, DealCreate(parcel_number="000000001"), limit=None)
    await add_deal(db_session, user_id, DealCreate(parcel_number="000000002"), limit=None)
    await update_deal(db_session, user_id, "000000001", DealUpdate(contact_phone="215-555-0100"))
    await db_session.flush()

    rows = {row[0]: row for row in await export_deals(db_session, user_id, row_limit=100)}
    # contact_name is column index 15, contact_phone 16
    assert rows["000000001"][16] == "215-555-0100"
    assert rows["000000002"][15] == "not traced"
    assert rows["000000002"][16] is None


async def test_the_export_refuses_a_pipeline_larger_than_it_can_compute(
    db_session: AsyncSession,
) -> None:
    """Every figure in the file is computed for the export, so the file is bounded."""
    from lotscope.core.errors import ValidationError
    from lotscope.pipeline.service import export_deals

    user_id = await _seed(db_session)
    for number in ("000000001", "000000002", "000000003"):
        await add_deal(db_session, user_id, DealCreate(parcel_number=number), limit=None)
    await db_session.flush()

    with pytest.raises(ValidationError) as caught:
        await export_deals(db_session, user_id, row_limit=2)

    assert "Narrow your search" in str(caught.value)

    within = await export_deals(db_session, user_id, row_limit=3)
    assert len(within) == 3
