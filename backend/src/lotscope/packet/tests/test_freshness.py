from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.buybox.schemas import BuyBoxWrite
from lotscope.buybox.service import write_buy_box
from lotscope.packet.schemas import PacketModel
from lotscope.packet.service import build_packet_model

pytestmark = pytest.mark.integration

SALE_DATE = date.today() + timedelta(days=21)
STALE_MAO = 999_999.0


async def _user(session: AsyncSession, email: str) -> int:
    await session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
            "VALUES (:e, 'x', 'user', 'pro', true)"
        ),
        {"e": email},
    )
    await session.flush()
    return int(await session.scalar(text("SELECT id FROM app_user WHERE email=:e"), {"e": email}))


async def _listing(session: AsyncSession, parcel: str) -> None:
    await session.execute(
        text(
            "INSERT INTO zoning_standard (code, code_version, market_code, min_lot_area_sqft, "
            "min_lot_width_ft, max_height_ft, max_occupancy_pct, permitted_uses, max_units) "
            "VALUES ('RSA-5', 'fresh-1', 'phl', 640, 16, 38, 75, "
            "'[\"single_family\"]'::jsonb, 3) ON CONFLICT DO NOTHING"
        )
    )
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code, address, base_zoning_code, "
            "market_value, lot_area_sqft, frontage_ft, is_vacant, geom_local) "
            "VALUES (:p, 'phl', '1 FRESH ST', 'RSA-5', 90000, 4000, 40, true, "
            "ST_SetSRID(ST_MakePoint(2690000, 240000), 2272))"
        ),
        {"p": parcel},
    )
    await session.execute(
        text(
            "INSERT INTO sheriff_sale (parcel_number, case_number, sale_type, sale_date, "
            "status, opening_bid) VALUES (:p, '2699-001', 'Tax', :d, 'Scheduled - Tax', 1600)"
        ),
        {"p": parcel, "d": SALE_DATE},
    )
    await session.flush()


async def test_a_stale_screening_row_does_not_change_the_packets_offer(
    db_session: AsyncSession,
) -> None:
    parcel = "phl:freshness1"
    await _listing(db_session, parcel)
    user_id = await _user(db_session, "freshness@example.com")
    await write_buy_box(db_session, user_id, BuyBoxWrite(min_lot_sqft=None, zoning_codes=[]))
    await db_session.flush()

    before = await build_packet_model(db_session, user_id, SALE_DATE)

    await db_session.execute(
        text(
            "INSERT INTO parcel_screen (parcel_number, max_allowable_offer, "
            "est_margin, can_build_by_right, by_right_units, computed_at) "
            "VALUES (:p, :mao, 0.99, true, 9, now() - interval '400 days')"
        ),
        {"p": parcel, "mao": STALE_MAO},
    )
    await db_session.flush()

    after = await build_packet_model(db_session, user_id, SALE_DATE)

    def offer(model: PacketModel) -> float | None:
        entries = {lot.parcel_number: lot for lot in model.lots}
        return entries[parcel].max_allowable_offer if parcel in entries else None

    assert [lot.parcel_number for lot in before.lots] == [lot.parcel_number for lot in after.lots]
    assert offer(before) == offer(after)
    assert offer(after) != STALE_MAO
    for model in (before, after):
        for lot in model.lots:
            assert lot.max_allowable_offer != STALE_MAO
            assert lot.by_right_units != 9


async def test_the_packet_states_when_it_was_computed_not_when_the_index_was(
    db_session: AsyncSession,
) -> None:
    parcel = "phl:freshness2"
    await _listing(db_session, parcel)
    user_id = await _user(db_session, "freshness2@example.com")
    await db_session.execute(
        text(
            "INSERT INTO parcel_screen (parcel_number, max_allowable_offer, "
            "computed_at) VALUES (:p, 1, now() - interval '400 days')"
        ),
        {"p": parcel},
    )
    await db_session.flush()

    model = await build_packet_model(db_session, user_id, SALE_DATE)

    # The packet stamps datetime.now(UTC), so compare against the UTC date. date.today()
    # is local, and the two disagree for eight hours of every day here.
    today_utc = datetime.now(UTC).date()
    assert model.header.computed_at.date() == today_utc
    for lot in model.lots:
        assert lot.computed_at.date() == today_utc
