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
from lotscope.verdict.composition import VERDICT_VERSION

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


async def test_list_deals_surfaces_verdict_economics(db_session: AsyncSession) -> None:
    user_id = await _seed(db_session)
    await db_session.execute(
        text(
            "INSERT INTO parcel_verdict "
            "(parcel_number, verdict_version, max_allowable_offer, arv, est_profit, "
            "est_margin, is_underpriced) "
            "VALUES ('000000001', :vv, 90000, 250000, 45000, 0.18, true)"
        ),
        {"vv": VERDICT_VERSION},
    )
    await add_deal(db_session, user_id, DealCreate(parcel_number="000000001"), limit=None)

    deal = (await list_deals(db_session, user_id))[0]
    assert deal.max_allowable_offer == 90000
    assert deal.arv == 250000
    assert deal.est_profit == 45000
    assert deal.is_underpriced is True


async def test_export_marks_untraced_deals_not_traced(db_session: AsyncSession) -> None:
    from lotscope.pipeline.service import export_deals

    user_id = await _seed(db_session)
    await add_deal(db_session, user_id, DealCreate(parcel_number="000000001"), limit=None)
    await add_deal(db_session, user_id, DealCreate(parcel_number="000000002"), limit=None)
    await update_deal(
        db_session, user_id, "000000001", DealUpdate(contact_phone="215-555-0100")
    )
    await db_session.flush()

    rows = {row[0]: row for row in await export_deals(db_session, user_id, row_limit=100)}
    # contact_name is column index 15, contact_phone 16
    assert rows["000000001"][16] == "215-555-0100"
    assert rows["000000002"][15] == "not traced"
    assert rows["000000002"][16] is None
