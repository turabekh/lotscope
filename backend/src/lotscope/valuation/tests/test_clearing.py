from datetime import date, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.valuation.service import (
    CLEARING_MINIMUM_SAMPLE,
    CLEARING_MONTHS,
    CLEARING_RADIUS_M,
    SHERIFF_DEED_DOCUMENT_TYPE,
    sheriff_clearing_estimate,
)

pytestmark = pytest.mark.integration

SUBJECT = "phl:clearing-subject"
NEAR_X, NEAR_Y = 2690000.0, 240000.0
FAR_X = NEAR_X + 20_000.0


async def _parcel(
    session: AsyncSession,
    parcel: str,
    *,
    zoning: str = "RSA5",
    vacant: bool = True,
    x: float = NEAR_X,
) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code, base_zoning_code, is_vacant, "
            "geom_local) VALUES (:p, 'phl', :z, :v, ST_SetSRID(ST_MakePoint(:x, :y), 2272))"
        ),
        {"p": parcel, "z": zoning, "v": vacant, "x": x, "y": NEAR_Y},
    )
    await session.flush()


async def _sale(
    session: AsyncSession,
    parcel: str,
    price: float,
    *,
    document_type: str = SHERIFF_DEED_DOCUMENT_TYPE,
    days_ago: int = 100,
) -> None:
    await session.execute(
        text(
            "INSERT INTO sale (parcel_number, sale_date, sale_price, document_type) "
            "VALUES (:p, :d, :price, :t)"
        ),
        {
            "p": parcel,
            "d": date.today() - timedelta(days=days_ago),
            "price": price,
            "t": document_type,
        },
    )
    await session.flush()


async def _neighbours(
    session: AsyncSession, prices: list[float], *, zoning: str = "RSA5", **sale_kwargs: object
) -> None:
    for index, price in enumerate(prices):
        parcel = f"phl:clearing-n{index}-{zoning}-{int(price)}"
        await _parcel(session, parcel, zoning=zoning)
        await _sale(session, parcel, price, **sale_kwargs)  # type: ignore[arg-type]


async def test_three_nearby_sheriff_deeds_are_enough_and_the_median_is_the_estimate(
    db_session: AsyncSession,
) -> None:
    await _parcel(db_session, SUBJECT)
    await _neighbours(db_session, [10_000.0, 20_000.0, 90_000.0])

    estimate = await sheriff_clearing_estimate(db_session, SUBJECT)

    assert estimate.sufficient is True
    assert estimate.sample_size == CLEARING_MINIMUM_SAMPLE == 3
    assert estimate.estimate == 20_000.0
    assert estimate.low == 10_000.0
    assert estimate.high == 90_000.0
    assert estimate.zoning_class == "RSA"
    assert estimate.radius_m == CLEARING_RADIUS_M
    assert estimate.months == CLEARING_MONTHS
    assert estimate.source_url.startswith("https://")
    assert estimate.reason is None


async def test_two_nearby_deeds_are_not_enough_and_the_reason_names_the_count(
    db_session: AsyncSession,
) -> None:
    await _parcel(db_session, SUBJECT)
    await _neighbours(db_session, [10_000.0, 20_000.0])

    estimate = await sheriff_clearing_estimate(db_session, SUBJECT)

    assert estimate.sufficient is False
    assert estimate.sample_size == 2
    assert estimate.estimate is None
    assert estimate.reason is not None
    assert "Only 2 sheriff's deeds" in estimate.reason
    assert "3 are needed" in estimate.reason


async def test_no_nearby_deeds_at_all_is_insufficient_not_an_error(
    db_session: AsyncSession,
) -> None:
    await _parcel(db_session, SUBJECT)

    estimate = await sheriff_clearing_estimate(db_session, SUBJECT)

    assert estimate.sufficient is False
    assert estimate.sample_size == 0
    assert estimate.estimate is None


async def test_ordinary_deeds_do_not_count_towards_the_clearing_sample(
    db_session: AsyncSession,
) -> None:
    await _parcel(db_session, SUBJECT)
    await _neighbours(db_session, [10_000.0, 20_000.0, 30_000.0], document_type="DEED")

    estimate = await sheriff_clearing_estimate(db_session, SUBJECT)

    assert estimate.sufficient is False
    assert estimate.sample_size == 0


async def test_a_different_zoning_class_does_not_count(db_session: AsyncSession) -> None:
    await _parcel(db_session, SUBJECT, zoning="RSA5")
    await _neighbours(db_session, [10_000.0, 20_000.0, 30_000.0], zoning="CMX2")

    estimate = await sheriff_clearing_estimate(db_session, SUBJECT)

    assert estimate.sufficient is False
    assert estimate.sample_size == 0


async def test_the_zoning_class_ignores_the_district_number(db_session: AsyncSession) -> None:
    await _parcel(db_session, SUBJECT, zoning="RSA5")
    await _neighbours(db_session, [10_000.0, 20_000.0, 30_000.0], zoning="RSA3")

    estimate = await sheriff_clearing_estimate(db_session, SUBJECT)

    assert estimate.sufficient is True
    assert estimate.zoning_class == "RSA"
    assert estimate.sample_size == 3


async def test_deeds_older_than_the_window_do_not_count(db_session: AsyncSession) -> None:
    await _parcel(db_session, SUBJECT)
    await _neighbours(db_session, [10_000.0, 20_000.0, 30_000.0], days_ago=1_000)

    estimate = await sheriff_clearing_estimate(db_session, SUBJECT)

    assert estimate.sufficient is False
    assert estimate.sample_size == 0


async def test_deeds_beyond_the_radius_do_not_count(db_session: AsyncSession) -> None:
    await _parcel(db_session, SUBJECT)
    for index, price in enumerate((10_000.0, 20_000.0, 30_000.0)):
        parcel = f"phl:clearing-far{index}"
        await _parcel(db_session, parcel, x=FAR_X)
        await _sale(db_session, parcel, price)

    estimate = await sheriff_clearing_estimate(db_session, SUBJECT)

    assert estimate.sufficient is False
    assert estimate.sample_size == 0


async def test_an_improved_parcel_does_not_count_as_land(db_session: AsyncSession) -> None:
    await _parcel(db_session, SUBJECT)
    for index, price in enumerate((10_000.0, 20_000.0, 30_000.0)):
        parcel = f"phl:clearing-house{index}"
        await _parcel(db_session, parcel, vacant=False)
        await _sale(db_session, parcel, price)

    estimate = await sheriff_clearing_estimate(db_session, SUBJECT)

    assert estimate.sufficient is False
    assert estimate.sample_size == 0
