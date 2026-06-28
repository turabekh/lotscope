import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.errors import NotFoundError, QuotaExceededError
from lotscope.pipeline.schemas import DealCreate, DealUpdate
from lotscope.pipeline.service import (
    add_deal,
    count_deals,
    get_deal,
    list_deals,
    remove_deal,
    update_deal,
)

pytestmark = pytest.mark.integration


async def _seed(session: AsyncSession) -> int:
    await session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
            "VALUES ('d@example.com', 'x', 'user', 'free', true)"
        )
    )
    user_id = await session.scalar(text("SELECT id FROM app_user WHERE email = 'd@example.com'"))
    for number in ("000000001", "000000002", "000000003"):
        await session.execute(
            text("INSERT INTO parcel (parcel_number, address) VALUES (:pn, :addr)"),
            {"pn": number, "addr": f"{number} Main St"},
        )
    await session.flush()
    return int(user_id)


async def test_add_defaults_to_lead_and_lists(db_session: AsyncSession) -> None:
    user_id = await _seed(db_session)
    await add_deal(
        db_session, user_id, DealCreate(parcel_number="000000001", target_price=120000), limit=10
    )
    deals = await list_deals(db_session, user_id)
    assert len(deals) == 1
    assert deals[0].stage == "lead"
    assert deals[0].target_price == 120000
    assert deals[0].address == "000000001 Main St"


async def test_add_is_idempotent_per_parcel(db_session: AsyncSession) -> None:
    user_id = await _seed(db_session)
    first = await add_deal(db_session, user_id, DealCreate(parcel_number="000000001"), limit=10)
    second = await add_deal(
        db_session, user_id, DealCreate(parcel_number="000000001", stage="offer"), limit=10
    )
    assert first.id == second.id
    assert await count_deals(db_session, user_id) == 1
    assert second.stage == "lead"  # existing deal returned unchanged


async def test_update_moves_stage(db_session: AsyncSession) -> None:
    user_id = await _seed(db_session)
    await add_deal(db_session, user_id, DealCreate(parcel_number="000000001"), limit=10)
    await update_deal(
        db_session, user_id, "000000001", DealUpdate(stage="under_contract", note="signed")
    )
    deal = await get_deal(db_session, user_id, "000000001")
    assert deal is not None
    assert deal.stage == "under_contract"
    assert deal.note == "signed"


async def test_limit_enforced(db_session: AsyncSession) -> None:
    user_id = await _seed(db_session)
    await add_deal(db_session, user_id, DealCreate(parcel_number="000000001"), limit=2)
    await add_deal(db_session, user_id, DealCreate(parcel_number="000000002"), limit=2)
    with pytest.raises(QuotaExceededError):
        await add_deal(db_session, user_id, DealCreate(parcel_number="000000003"), limit=2)


async def test_add_unknown_parcel_and_update_missing(db_session: AsyncSession) -> None:
    user_id = await _seed(db_session)
    with pytest.raises(NotFoundError):
        await add_deal(db_session, user_id, DealCreate(parcel_number="999999999"), limit=10)
    with pytest.raises(NotFoundError):
        await update_deal(db_session, user_id, "000000001", DealUpdate(stage="offer"))


async def test_remove(db_session: AsyncSession) -> None:
    user_id = await _seed(db_session)
    await add_deal(db_session, user_id, DealCreate(parcel_number="000000001"), limit=10)
    assert await remove_deal(db_session, user_id, "000000001") is True
    assert await remove_deal(db_session, user_id, "000000001") is False
    assert await count_deals(db_session, user_id) == 0
