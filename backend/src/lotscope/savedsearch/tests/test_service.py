import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.errors import NotFoundError, QuotaExceededError
from lotscope.savedsearch.schemas import SavedSearchCreate, SavedSearchUpdate, SearchCriteria
from lotscope.savedsearch.service import (
    create_search,
    delete_search,
    get_search,
    list_searches,
    pending_alerts_for_user,
    refresh_search,
    run_user_matches,
    update_search,
)

pytestmark = pytest.mark.integration


async def _user(session: AsyncSession, email: str = "s@example.com") -> int:
    await session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
            "VALUES (:email, 'x', 'user', 'free', true)"
        ),
        {"email": email},
    )
    user_id = await session.scalar(
        text("SELECT id FROM app_user WHERE email = :email"), {"email": email}
    )
    return int(user_id)


async def _parcel(
    session: AsyncSession, number: str, *, vacant: bool = True, zoning: str = "RSA-5"
) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, address, base_zoning_code, is_vacant, "
            "is_city_owned, market_value) "
            "VALUES (:pn, :addr, :z, :v, false, 50000)"
        ),
        {"pn": number, "addr": f"{number} Main St", "z": zoning, "v": vacant},
    )
    await session.flush()


async def test_create_runs_baseline_no_pending(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _parcel(db_session, "000000001")
    await _parcel(db_session, "000000002")

    search = await create_search(
        db_session,
        user_id,
        SavedSearchCreate(name="Vacant RSA", criteria=SearchCriteria(vacant_only=True)),
        limit=None,
    )

    detail = await get_search(db_session, user_id, search.id)
    assert detail.match_count == 2
    assert detail.new_count == 0
    assert all(not match.is_new for match in detail.matches)
    assert await pending_alerts_for_user(db_session, user_id) == []


async def test_new_parcel_becomes_pending_alert(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _parcel(db_session, "000000001")
    search = await create_search(
        db_session,
        user_id,
        SavedSearchCreate(name="Vacant", criteria=SearchCriteria(vacant_only=True)),
        limit=None,
    )

    await _parcel(db_session, "000000002")
    await run_user_matches(db_session, user_id)

    alerts = await pending_alerts_for_user(db_session, user_id)
    assert len(alerts) == 1
    assert [m.parcel_number for m in alerts[0].new_matches] == ["000000002"]

    detail = await get_search(db_session, user_id, search.id)
    assert detail.match_count == 2
    assert detail.new_count == 1


async def test_non_matching_parcel_is_ignored(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _parcel(db_session, "000000001")
    search = await create_search(
        db_session,
        user_id,
        SavedSearchCreate(name="RM only", criteria=SearchCriteria(zoning_codes=["RM-1"])),
        limit=None,
    )
    detail = await get_search(db_session, user_id, search.id)
    assert detail.match_count == 0


async def test_zoning_criteria_matches_resolved_only_parcel(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await db_session.execute(
        text(
            "INSERT INTO parcel "
            "(parcel_number, address, base_zoning_code, resolved_zoning_code, is_vacant, "
            "is_city_owned, market_value) "
            "VALUES ('000000901', '1 A ST', '', 'RM', true, false, 50000)"
        )
    )
    search = await create_search(
        db_session,
        user_id,
        SavedSearchCreate(name="RM only", criteria=SearchCriteria(zoning_codes=["RM"])),
        limit=None,
    )

    detail = await get_search(db_session, user_id, search.id)
    assert detail.match_count == 1
    assert [m.parcel_number for m in detail.matches] == ["000000901"]
    assert detail.matches[0].base_zoning_code == "RM"


async def test_limit_enforced(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await create_search(db_session, user_id, SavedSearchCreate(name="a"), limit=1)
    with pytest.raises(QuotaExceededError):
        await create_search(db_session, user_id, SavedSearchCreate(name="b"), limit=1)


async def test_update_criteria_resets_matches(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _parcel(db_session, "000000001", zoning="RSA-5")
    await _parcel(db_session, "000000002", zoning="RM-1")
    search = await create_search(
        db_session,
        user_id,
        SavedSearchCreate(name="RSA", criteria=SearchCriteria(zoning_codes=["RSA-5"])),
        limit=None,
    )
    assert (await get_search(db_session, user_id, search.id)).match_count == 1

    await update_search(
        db_session,
        user_id,
        search.id,
        SavedSearchUpdate(criteria=SearchCriteria(zoning_codes=["RM-1"])),
    )
    detail = await get_search(db_session, user_id, search.id)
    assert [m.parcel_number for m in detail.matches] == ["000000002"]
    assert detail.new_count == 0


async def test_refresh_acknowledges_then_clears(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _parcel(db_session, "000000001")
    search = await create_search(
        db_session,
        user_id,
        SavedSearchCreate(name="Vacant", criteria=SearchCriteria(vacant_only=True)),
        limit=None,
    )
    await _parcel(db_session, "000000002")
    await run_user_matches(db_session, user_id)
    assert (await get_search(db_session, user_id, search.id)).new_count == 1

    from lotscope.savedsearch.service import mark_user_notified

    await mark_user_notified(db_session, user_id)
    assert (await get_search(db_session, user_id, search.id)).new_count == 0


async def test_listing_and_ownership(db_session: AsyncSession) -> None:
    owner = await _user(db_session, "owner@example.com")
    other = await _user(db_session, "other@example.com")
    search = await create_search(db_session, owner, SavedSearchCreate(name="mine"), limit=None)

    assert len(await list_searches(db_session, owner)) == 1
    assert len(await list_searches(db_session, other)) == 0
    with pytest.raises(NotFoundError):
        await get_search(db_session, other, search.id)
    assert await delete_search(db_session, other, search.id) is False
    assert await delete_search(db_session, owner, search.id) is True


async def test_refresh_returns_detail(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _parcel(db_session, "000000001")
    search = await create_search(
        db_session,
        user_id,
        SavedSearchCreate(name="Vacant", criteria=SearchCriteria(vacant_only=True)),
        limit=None,
    )
    detail = await refresh_search(db_session, user_id, search.id)
    assert detail.id == search.id
