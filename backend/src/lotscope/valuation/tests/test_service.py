from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.valuation.service import value_parcel

pytestmark = pytest.mark.integration

_SINCE = date(2000, 1, 1)


async def _add_subject(
    session: AsyncSession, parcel_number: str, area: float, *, zoning: str | None = None
) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, lot_area_sqft, base_zoning_code, geom_2272) VALUES "
            "(:pn, :area, :zoning, ST_GeomFromText('POLYGON((0 0,0 5,5 5,5 0,0 0))', 2272))"
        ),
        {"pn": parcel_number, "area": area, "zoning": zoning},
    )


async def _add_comp(
    session: AsyncSession,
    parcel_number: str,
    *,
    offset_ft: float,
    area: float,
    price: float,
    vacant: bool = True,
    zoning: str | None = None,
    grantor: str | None = None,
    grantee: str | None = None,
) -> None:
    geom = (
        f"POLYGON(({offset_ft} 0,{offset_ft} 5,{offset_ft + 5} 5,{offset_ft + 5} 0,{offset_ft} 0))"
    )
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, lot_area_sqft, is_vacant, base_zoning_code, "
            "geom_2272) VALUES (:pn, :area, :vacant, :zoning, ST_GeomFromText(:geom, 2272))"
        ),
        {"pn": parcel_number, "area": area, "vacant": vacant, "zoning": zoning, "geom": geom},
    )
    await session.execute(
        text(
            "INSERT INTO sale "
            "(parcel_number, document_id, sale_price, sale_date, grantor, grantee) "
            "VALUES (:pn, :doc, :price, '2025-01-01', :grantor, :grantee)"
        ),
        {
            "pn": parcel_number,
            "doc": f"DOC-{parcel_number}",
            "price": price,
            "grantor": grantor,
            "grantee": grantee,
        },
    )


async def test_value_parcel_estimates_from_nearby_comps(db_session: AsyncSession) -> None:
    await _add_subject(db_session, "000000001", 2000)
    for index in range(5):
        await _add_comp(
            db_session, f"0000001{index}", offset_ft=50 * (index + 1), area=1000, price=100000
        )
    await db_session.flush()

    result = await value_parcel(db_session, "000000001", since=_SINCE)
    assert result is not None
    assert result.comp_count == 5
    assert result.estimate == 200000.0
    assert result.price_per_sqft == 100.0
    assert result.confidence == "high"
    assert result.sources[0]["source"] == "rtt_summary"


async def test_value_parcel_excludes_far_and_non_vacant_comps(db_session: AsyncSession) -> None:
    await _add_subject(db_session, "000000001", 2000)
    await _add_comp(db_session, "000000010", offset_ft=50, area=1000, price=100000)
    await _add_comp(db_session, "000000011", offset_ft=9000, area=1000, price=100000)
    await _add_comp(db_session, "000000012", offset_ft=80, area=1000, price=100000, vacant=False)
    await db_session.flush()

    result = await value_parcel(db_session, "000000001", since=_SINCE)
    assert result is not None
    assert result.comp_count == 1
    assert result.comps[0].parcel_number == "000000010"


async def test_value_parcel_excludes_related_party_sales(db_session: AsyncSession) -> None:
    await _add_subject(db_session, "000000001", 2000)
    for index in range(4):
        await _add_comp(
            db_session,
            f"0000001{index}",
            offset_ft=50 * (index + 1),
            area=1000,
            price=100000,
            grantor=f"SELLER PERSON{index}",
            grantee=f"BUYER OTHER{index}",
        )
    await _add_comp(
        db_session,
        "000000020",
        offset_ft=60,
        area=1000,
        price=10000,
        grantor="NGUYEN MINH",
        grantee="NGUYEN LAN",
    )
    await db_session.flush()

    result = await value_parcel(db_session, "000000001", since=_SINCE)
    assert result is not None
    assert result.comp_count == 4
    assert "000000020" not in {comp.parcel_number for comp in result.comps}
    assert any("related-party" in reason.lower() for reason in result.reasons)


async def test_value_parcel_segments_comps_by_use_class(db_session: AsyncSession) -> None:
    await _add_subject(db_session, "000000001", 2000, zoning="RSA5")
    await _add_comp(db_session, "000000010", offset_ft=50, area=1000, price=100000, zoning="RSA5")
    await _add_comp(db_session, "000000011", offset_ft=60, area=1000, price=20000000, zoning="CMX3")
    await db_session.flush()

    result = await value_parcel(db_session, "000000001", since=_SINCE)
    assert result is not None
    assert result.comp_count == 1
    assert result.comps[0].parcel_number == "000000010"
    assert result.estimate == 200000.0
    assert result.sources[0]["use_class"] == "residential"


async def test_value_parcel_can_disable_use_class_segmentation(db_session: AsyncSession) -> None:
    await _add_subject(db_session, "000000001", 2000, zoning="RSA5")
    await _add_comp(db_session, "000000010", offset_ft=50, area=1000, price=100000, zoning="RSA5")
    await _add_comp(db_session, "000000011", offset_ft=60, area=1000, price=20000000, zoning="CMX3")
    await db_session.flush()

    result = await value_parcel(db_session, "000000001", since=_SINCE, segment_by_use_class=False)
    assert result is not None
    assert result.comp_count == 2


async def test_value_parcel_without_comps_is_unknown(db_session: AsyncSession) -> None:
    await _add_subject(db_session, "000000001", 2000)
    await db_session.flush()

    result = await value_parcel(db_session, "000000001", since=_SINCE)
    assert result is not None
    assert result.estimate is None
    assert result.confidence == "low"
    assert result.comp_count == 0


async def test_value_parcel_returns_none_when_missing(db_session: AsyncSession) -> None:
    assert await value_parcel(db_session, "999999999", since=_SINCE) is None
