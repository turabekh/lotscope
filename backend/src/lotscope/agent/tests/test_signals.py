"""The overnight signal builder, one fixture per kind, plus idempotency.

A signal that fires twice is a brief that repeats itself; a signal that never fires is a
buyer who finds out at the auction. Both are worth a test.
"""

import json
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.agent.signal_builder import area_clause, build_signals
from lotscope.agent.signals import AnalystSignal
from lotscope.buybox.service import read_buy_box

pytestmark = pytest.mark.integration

TODAY = date(2026, 9, 5)
SINCE = datetime(2026, 9, 4, 4, 0, tzinfo=UTC)
OWNED = "phl:own0001"
NEIGHBOR = "phl:nbr0001"
FOLLOWED = "phl:fol0001"


async def _user(session: AsyncSession, email: str) -> int:
    return int(
        await session.scalar(
            text(
                "INSERT INTO app_user (email, hashed_password, role, tier, is_active, "
                "email_verified_at) VALUES (:e, 'x', 'user', 'user', true, now()) RETURNING id"
            ),
            {"e": email},
        )
    )


async def _parcel(
    session: AsyncSession, parcel: str, address: str, *, x: int = 2690000, y: int = 240000
) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code, address, owner, zip_code, "
            "is_vacant, lot_area_sqft, base_zoning_code, geom_local, geom_4326) VALUES "
            "(:p, 'phl', :a, 'ACME LLC', '19125', true, 1200, 'RSA-5', "
            "ST_SetSRID(ST_MakePoint(:x, :y), 2272), "
            "ST_SetSRID(ST_MakePoint(-75.14, 39.99), 4326))"
        ),
        {"p": parcel, "a": address, "x": x, "y": y},
    )
    await session.flush()


async def _buy_box(session: AsyncSession, user_id: int, owned: list[str]) -> None:
    await session.execute(
        text(
            "INSERT INTO buy_box (user_id, areas, target_use, owned_parcels, zoning_codes, "
            "assumptions) VALUES (:u, '[]'::jsonb, 'build', cast(:owned AS jsonb), "
            "'[]'::jsonb, '{}'::jsonb)"
        ),
        {"u": user_id, "owned": json.dumps(owned)},
    )
    await session.flush()


async def _setup(session: AsyncSession, email: str) -> int:
    user_id = await _user(session, email)
    await _parcel(session, OWNED, "1 OWNED ST")
    # Two feet away, so the adjacency predicate finds it.
    await _parcel(session, NEIGHBOR, "3 OWNED ST", x=2690002)
    await _parcel(session, FOLLOWED, "9 FOLLOWED ST", x=2695000, y=245000)
    await _buy_box(session, user_id, [OWNED])
    return user_id


async def _build(session: AsyncSession, user_id: int) -> list[AnalystSignal]:
    buy_box = await read_buy_box(session, user_id)
    return await build_signals(
        session, user_id=user_id, buy_box=buy_box, on_date=TODAY, since=SINCE
    )


# --- area clause -------------------------------------------------------------------------


def test_no_areas_means_the_whole_city_not_nothing() -> None:
    clause, params = area_clause((), "p")
    assert clause == "TRUE"
    assert params == {}


def test_zip_areas_become_a_zip_filter() -> None:
    clause, params = area_clause(({"name": "Fishtown", "zip_codes": ["19125"]},), "p")
    assert "zip_code" in clause
    assert params["zips_0"] == ["19125"]


# --- one test per signal kind ------------------------------------------------------------


async def test_a_sale_status_change_on_a_followed_lot_becomes_a_signal(
    db_session: AsyncSession,
) -> None:
    user_id = await _setup(db_session, "sig-sale@example.com")
    await db_session.execute(
        text("INSERT INTO deal (user_id, parcel_number, stage) VALUES (:u, :p, 'lead')"),
        {"u": user_id, "p": FOLLOWED},
    )
    await db_session.execute(
        text(
            "INSERT INTO sheriff_sale_event (parcel_number, case_number, old_status, "
            "new_status, observed_at) VALUES (:p, '2601-001', 'Active', 'Postponed', :at)"
        ),
        {"p": FOLLOWED, "at": datetime(2026, 9, 5, 5, 0, tzinfo=UTC)},
    )
    await db_session.flush()

    signals = await _build(db_session, user_id)

    assert [s.kind for s in signals] == ["sale_status"]
    assert "postponed" in signals[0].headline.lower()
    assert signals[0].source_table == "sheriff_sale_event"
    assert signals[0].source_row_id


async def test_a_new_violation_next_door_becomes_a_signal(db_session: AsyncSession) -> None:
    user_id = await _setup(db_session, "sig-viol@example.com")
    await db_session.execute(
        text(
            "INSERT INTO li_event (parcel_number, external_id, event_type, status, "
            "case_status, event_date, description, created_at) VALUES "
            "(:p, 'V9', 'violation', 'OPEN', 'IN VIOLATION', :d, 'DANGEROUS WALL', :at)"
        ),
        {
            "p": NEIGHBOR,
            "d": date(2026, 9, 4),
            "at": datetime(2026, 9, 5, 5, 0, tzinfo=UTC),
        },
    )
    await db_session.flush()

    signals = await _build(db_session, user_id)

    assert [s.kind for s in signals] == ["neighbor_violation"]
    assert signals[0].parcel_number == NEIGHBOR
    assert signals[0].source_table == "li_event"


async def test_a_neighbour_falling_delinquent_becomes_a_signal(db_session: AsyncSession) -> None:
    user_id = await _setup(db_session, "sig-delq@example.com")
    await db_session.execute(
        text(
            "INSERT INTO tax_status (parcel_number, is_delinquent, total_due, "
            "delinquency_owner, updated_at) VALUES (:p, true, 9500, 'PRIOR OWNER', :at)"
        ),
        {"p": NEIGHBOR, "at": datetime(2026, 9, 5, 5, 0, tzinfo=UTC)},
    )
    await db_session.flush()

    signals = await _build(db_session, user_id)

    assert [s.kind for s in signals] == ["neighbor_delinquency"]
    assert "9,500" in signals[0].headline


async def test_a_deed_next_door_becomes_a_signal(db_session: AsyncSession) -> None:
    user_id = await _setup(db_session, "sig-deed@example.com")
    await db_session.execute(
        text(
            "INSERT INTO sale (parcel_number, document_id, document_type, sale_date, "
            "sale_price, grantor, grantee, created_at) VALUES "
            "(:p, 'D1', 'DEED', :d, 61000, 'A', 'NEW NEIGHBOUR LLC', :at)"
        ),
        {
            "p": NEIGHBOR,
            "d": date(2026, 9, 3),
            "at": datetime(2026, 9, 5, 5, 0, tzinfo=UTC),
        },
    )
    await db_session.flush()

    signals = await _build(db_session, user_id)

    assert [s.kind for s in signals] == ["neighbor_deed"]
    assert "NEW NEIGHBOUR LLC" in signals[0].headline
    assert "61,000" in signals[0].headline


async def test_a_zoning_appeal_in_the_buy_box_becomes_a_signal(db_session: AsyncSession) -> None:
    user_id = await _setup(db_session, "sig-zba@example.com")
    await db_session.execute(
        text(
            "INSERT INTO zba_appeal (appeal_number, parcel_number, appeal_type, decision, "
            "address, created_at) VALUES ('ZBA-1', :p, 'USE', 'GRANTED', '9 FOLLOWED ST', :at)"
        ),
        {"p": FOLLOWED, "at": datetime(2026, 9, 5, 5, 0, tzinfo=UTC)},
    )
    await db_session.flush()

    signals = await _build(db_session, user_id)

    assert [s.kind for s in signals] == ["zba_filing"]
    assert signals[0].source_table == "zba_appeal"


async def test_a_new_listing_in_the_buy_box_becomes_a_signal(db_session: AsyncSession) -> None:
    user_id = await _setup(db_session, "sig-listing@example.com")
    await db_session.execute(
        text(
            "INSERT INTO sheriff_sale (parcel_number, case_number, sale_date, opening_bid, "
            "created_at) VALUES (:p, '2601-777', :d, 1500, :at)"
        ),
        {
            "p": FOLLOWED,
            "d": date(2026, 10, 7),
            "at": datetime(2026, 9, 5, 5, 0, tzinfo=UTC),
        },
    )
    await db_session.flush()

    signals = await _build(db_session, user_id)

    assert [s.kind for s in signals] == ["new_listing"]
    # It has not been screened, and the headline must not imply it has.
    assert signals[0].detail["screened"] is False
    assert "BID" not in signals[0].headline


async def test_a_create_alert_target_produces_a_signal_carrying_the_alert(
    db_session: AsyncSession,
) -> None:
    user_id = await _setup(db_session, "sig-alert@example.com")
    alert_id = int(
        await db_session.scalar(
            text(
                "INSERT INTO agent_alert (user_id, kind, scope, target, is_active) VALUES "
                "(:u, 'sale_status', 'parcel', :t, true) RETURNING id"
            ),
            {"u": user_id, "t": json.dumps({"parcel_number": FOLLOWED})},
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO sheriff_sale_event (parcel_number, case_number, old_status, "
            "new_status, observed_at) VALUES (:p, '2601-002', 'Active', 'Stayed', :at)"
        ),
        {"p": FOLLOWED, "at": datetime(2026, 9, 5, 5, 0, tzinfo=UTC)},
    )
    await db_session.flush()

    signals = await _build(db_session, user_id)

    assert [s.kind for s in signals] == ["sale_status"]
    assert signals[0].detail["alert_id"] == alert_id


# --- idempotency -------------------------------------------------------------------------


async def test_building_twice_writes_the_row_once(db_session: AsyncSession) -> None:
    user_id = await _setup(db_session, "sig-idem@example.com")
    await db_session.execute(
        text("INSERT INTO deal (user_id, parcel_number, stage) VALUES (:u, :p, 'lead')"),
        {"u": user_id, "p": FOLLOWED},
    )
    await db_session.execute(
        text(
            "INSERT INTO sheriff_sale_event (parcel_number, case_number, old_status, "
            "new_status, observed_at) VALUES (:p, '2601-003', 'Active', 'Postponed', :at)"
        ),
        {"p": FOLLOWED, "at": datetime(2026, 9, 5, 5, 0, tzinfo=UTC)},
    )
    await db_session.flush()

    first = await _build(db_session, user_id)
    second = await _build(db_session, user_id)

    assert len(first) == 1
    assert second == []
    stored = await db_session.scalar(
        text("SELECT count(*) FROM analyst_signal WHERE user_id = :u"), {"u": user_id}
    )
    assert stored == 1


async def test_a_change_older_than_the_window_is_not_a_signal(db_session: AsyncSession) -> None:
    user_id = await _setup(db_session, "sig-old@example.com")
    await db_session.execute(
        text("INSERT INTO deal (user_id, parcel_number, stage) VALUES (:u, :p, 'lead')"),
        {"u": user_id, "p": FOLLOWED},
    )
    await db_session.execute(
        text(
            "INSERT INTO sheriff_sale_event (parcel_number, case_number, old_status, "
            "new_status, observed_at) VALUES (:p, '2601-004', 'Active', 'Postponed', :at)"
        ),
        {"p": FOLLOWED, "at": SINCE - timedelta(days=5)},
    )
    await db_session.flush()

    assert await _build(db_session, user_id) == []


async def test_a_lot_the_buyer_does_not_follow_produces_nothing(db_session: AsyncSession) -> None:
    user_id = await _setup(db_session, "sig-unfollowed@example.com")
    await _parcel(db_session, "phl:stranger", "99 STRANGER ST", x=2699000, y=249000)
    await db_session.execute(
        text(
            "INSERT INTO sheriff_sale_event (parcel_number, case_number, old_status, "
            "new_status, observed_at) VALUES ('phl:stranger', '2601-005', 'Active', "
            "'Postponed', :at)"
        ),
        {"at": datetime(2026, 9, 5, 5, 0, tzinfo=UTC)},
    )
    await db_session.flush()

    assert await _build(db_session, user_id) == []
