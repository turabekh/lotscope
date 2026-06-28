import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.errors import NotFoundError, QuotaExceededError
from lotscope.watchlist.schemas import SavedParcelCreate, SavedParcelUpdate
from lotscope.watchlist.service import (
    acknowledge,
    add_saved,
    count_saved,
    is_saved,
    list_saved,
    remove_saved,
    update_saved,
)

pytestmark = pytest.mark.integration


async def _seed(session: AsyncSession) -> int:
    await session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
            "VALUES ('w@example.com', 'x', 'user', 'free', true) RETURNING id"
        )
    )
    user_id = await session.scalar(text("SELECT id FROM app_user WHERE email = 'w@example.com'"))
    for number in ("000000001", "000000002", "000000003"):
        await session.execute(
            text("INSERT INTO parcel (parcel_number, address) VALUES (:pn, :addr)"),
            {"pn": number, "addr": f"{number} Main St"},
        )
    await session.flush()
    return int(user_id)


async def test_add_and_list(db_session: AsyncSession) -> None:
    user_id = await _seed(db_session)
    await add_saved(
        db_session,
        user_id,
        SavedParcelCreate(parcel_number="000000001", tags=["teardown"], note="call broker"),
        limit=25,
    )
    assert await is_saved(db_session, user_id, "000000001") is True
    assert await count_saved(db_session, user_id) == 1

    items = await list_saved(db_session, user_id)
    assert len(items) == 1
    assert items[0].address == "000000001 Main St"
    assert items[0].tags == ["teardown"]
    assert items[0].note == "call broker"


async def test_add_is_idempotent_upsert(db_session: AsyncSession) -> None:
    user_id = await _seed(db_session)
    await add_saved(db_session, user_id, SavedParcelCreate(parcel_number="000000001"), limit=25)
    await add_saved(
        db_session,
        user_id,
        SavedParcelCreate(parcel_number="000000001", tags=["flip"], note="updated"),
        limit=25,
    )
    assert await count_saved(db_session, user_id) == 1
    items = await list_saved(db_session, user_id)
    assert items[0].tags == ["flip"]
    assert items[0].note == "updated"


async def test_limit_enforced(db_session: AsyncSession) -> None:
    user_id = await _seed(db_session)
    await add_saved(db_session, user_id, SavedParcelCreate(parcel_number="000000001"), limit=2)
    await add_saved(db_session, user_id, SavedParcelCreate(parcel_number="000000002"), limit=2)

    with pytest.raises(QuotaExceededError):
        await add_saved(db_session, user_id, SavedParcelCreate(parcel_number="000000003"), limit=2)

    # re-saving an existing parcel at the cap is allowed
    await add_saved(
        db_session, user_id, SavedParcelCreate(parcel_number="000000001", tags=["x"]), limit=2
    )


async def test_add_unknown_parcel_raises(db_session: AsyncSession) -> None:
    user_id = await _seed(db_session)
    with pytest.raises(NotFoundError):
        await add_saved(db_session, user_id, SavedParcelCreate(parcel_number="999999999"), limit=25)


async def test_update_and_remove(db_session: AsyncSession) -> None:
    user_id = await _seed(db_session)
    await add_saved(db_session, user_id, SavedParcelCreate(parcel_number="000000001"), limit=25)

    await update_saved(
        db_session, user_id, "000000001", SavedParcelUpdate(tags=["watch"], note="hot")
    )
    items = await list_saved(db_session, user_id)
    assert items[0].tags == ["watch"]
    assert items[0].note == "hot"

    assert await remove_saved(db_session, user_id, "000000001") is True
    assert await count_saved(db_session, user_id) == 0
    assert await remove_saved(db_session, user_id, "000000001") is False


async def test_update_missing_raises(db_session: AsyncSession) -> None:
    user_id = await _seed(db_session)
    with pytest.raises(NotFoundError):
        await update_saved(db_session, user_id, "000000001", SavedParcelUpdate(note="x"))


async def test_change_alerts_detected_and_acknowledged(db_session: AsyncSession) -> None:
    user_id = await _seed(db_session)
    await add_saved(db_session, user_id, SavedParcelCreate(parcel_number="000000001"), limit=25)

    # at save time there were no signals; now the parcel becomes distressed
    await db_session.execute(
        text(
            "INSERT INTO tax_status (parcel_number, is_delinquent, total_due, in_sheriff_sale) "
            "VALUES ('000000001', true, 12000, true)"
        )
    )
    await db_session.flush()

    items = await list_saved(db_session, user_id)
    item = items[0]
    assert item.has_alerts is True
    codes = {change.code for change in item.changes}
    assert {"sheriff_sale", "delinquent"} <= codes

    # marking seen re-snapshots, clearing the alerts
    await acknowledge(db_session, user_id, "000000001")
    after = await list_saved(db_session, user_id)
    assert after[0].has_alerts is False
    assert after[0].changes == []
