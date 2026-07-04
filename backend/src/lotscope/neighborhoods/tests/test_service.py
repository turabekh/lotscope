import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.neighborhoods.service import neighborhood_market_stats

pytestmark = pytest.mark.integration


async def _neighborhood(session: AsyncSession, name: str, wkt: str) -> None:
    await session.execute(
        text(
            "INSERT INTO neighborhood (name, geom_2272) VALUES (:name, ST_GeomFromText(:wkt, 2272))"
        ),
        {"name": name, "wkt": wkt},
    )


async def _vacant_parcel(
    session: AsyncSession,
    number: str,
    *,
    x: float,
    y: float,
    market_value: int,
    delinquent: bool = False,
    sheriff: bool = False,
    distress: int | None = None,
) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, is_vacant, market_value, geom_2272) VALUES "
            "(:pn, true, :mv, ST_GeomFromText(:wkt, 2272))"
        ),
        {
            "pn": number,
            "mv": market_value,
            "wkt": f"POLYGON(({x} {y},{x} {y + 2},{x + 2} {y + 2},{x + 2} {y},{x} {y}))",
        },
    )
    if delinquent or sheriff:
        await session.execute(
            text(
                "INSERT INTO tax_status (parcel_number, is_delinquent, in_sheriff_sale) "
                "VALUES (:pn, :d, :s)"
            ),
            {"pn": number, "d": delinquent, "s": sheriff},
        )
    if distress is not None:
        await session.execute(
            text(
                "INSERT INTO parcel_distress (parcel_number, score, tier, version) "
                "VALUES (:pn, :score, 'high', 'v2')"
            ),
            {"pn": number, "score": distress},
        )


async def test_market_stats_aggregate_per_neighborhood(db_session: AsyncSession) -> None:
    await _neighborhood(db_session, "Alpha", "POLYGON((0 0,0 100,100 100,100 0,0 0))")
    await _neighborhood(db_session, "Beta", "POLYGON((200 0,200 100,300 100,300 0,200 0))")
    await _vacant_parcel(
        db_session, "000000001", x=10, y=10, market_value=40000, delinquent=True, distress=60
    )
    await _vacant_parcel(
        db_session, "000000002", x=20, y=20, market_value=60000, sheriff=True, distress=40
    )
    await _vacant_parcel(db_session, "000000003", x=210, y=10, market_value=30000, distress=20)
    await db_session.flush()

    result = await neighborhood_market_stats(db_session)

    assert result.totals.neighborhoods == 2
    assert result.totals.vacant_lots == 3
    assert result.totals.tax_delinquent == 1
    assert result.totals.sheriff_sale == 1

    by_name = {n.name: n for n in result.neighborhoods}
    assert by_name["Alpha"].vacant_lots == 2
    assert by_name["Alpha"].median_market_value == 50000
    assert by_name["Alpha"].avg_distress == 50.0
    assert by_name["Alpha"].tax_delinquent == 1
    assert by_name["Beta"].vacant_lots == 1
    assert by_name["Beta"].tax_delinquent == 0

    # Ordered by vacant_lots desc
    assert result.neighborhoods[0].name == "Alpha"


async def test_market_stats_excludes_empty_neighborhoods(db_session: AsyncSession) -> None:
    await _neighborhood(db_session, "Empty", "POLYGON((0 0,0 10,10 10,10 0,0 0))")
    await db_session.flush()

    result = await neighborhood_market_stats(db_session)
    assert result.neighborhoods == []
    assert result.totals.vacant_lots == 0
