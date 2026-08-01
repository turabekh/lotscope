import asyncio
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.logging import configure_logging, get_logger
from lotscope.verdict.service import recompute_verdicts

MARKET_CODE = "phl"
LOCAL_SRID = 2272
SOURCE = "e2e"
PARCEL_NUMBERS = [f"{MARKET_CODE}:9990000{index}" for index in range(1, 6)]

PARCEL_ROWS = [
    ("99900001", "1500 E2E FIXTURE WAY", "Acme Land Holdings LLC", 1600, 18, 90, 120000, True),
    ("99900002", "1502 E2E FIXTURE WAY", "Jane Smith", 1000, 16, 62, 90000, True),
    ("99900003", "1504 E2E FIXTURE WAY", "John Developer", 1100, 16, 68, 95000, True),
    ("99900004", "1506 E2E FIXTURE WAY", "Smith Family Trust", 1050, 16, 65, 92000, True),
    ("99900005", "1508 E2E FIXTURE WAY", "City of Philadelphia", 2000, 20, 100, 140000, True),
]

COMP_SALES = [
    ("99900002", "E2E-2", date(2025, 5, 1), 95000),
    ("99900003", "E2E-3", date(2025, 6, 15), 110000),
    ("99900004", "E2E-4", date(2025, 7, 20), 100000),
]

DISTRICT_POLYGON = (
    "POLYGON((-75.170 39.925,-75.170 39.935,-75.160 39.935,-75.160 39.925,-75.170 39.925))"
)


def _parcel_polygon(index: int) -> str:
    west = -75.1650 + index * 0.0003
    east = west + 0.0002
    return f"POLYGON(({west} 39.9300,{west} 39.9302,{east} 39.9302,{east} 39.9300,{west} 39.9300))"


async def _clear(session: AsyncSession) -> None:
    for table in ("parcel_verdict", "sale", "tax_status", "parcel"):
        await session.execute(
            text(f"DELETE FROM {table} WHERE parcel_number = ANY(:numbers)"),
            {"numbers": PARCEL_NUMBERS},
        )
    await session.execute(
        text("DELETE FROM zoning_district WHERE market_code = :market AND external_id = :source"),
        {"market": MARKET_CODE, "source": SOURCE},
    )


async def _insert_district(session: AsyncSession) -> None:
    await session.execute(
        text(
            "INSERT INTO zoning_district (external_id, code, category, market_code, geom_local) "
            "VALUES (:source, 'RSA-5', 'Residential', :market, "
            "ST_Transform(ST_GeomFromText(:polygon, 4326), CAST(:srid AS integer)))"
        ),
        {
            "source": SOURCE,
            "market": MARKET_CODE,
            "polygon": DISTRICT_POLYGON,
            "srid": LOCAL_SRID,
        },
    )


async def _insert_parcels(session: AsyncSession) -> None:
    for index, row in enumerate(PARCEL_ROWS, start=1):
        local_key, address, owner, area, frontage, depth, value, vacant = row
        await session.execute(
            text(
                "INSERT INTO parcel (parcel_number, market_code, address, owner, "
                "base_zoning_code, lot_area_sqft, frontage_ft, depth_ft, market_value, "
                "land_value, is_vacant, is_city_owned, geom_4326, geom_local) "
                "VALUES (:number, :market, :address, :owner, 'RSA-5', :area, "
                ":frontage, :depth, :value, :land_value, :vacant, :city_owned, "
                "ST_GeomFromText(:polygon, 4326), "
                "ST_Transform(ST_GeomFromText(:polygon, 4326), CAST(:srid AS integer)))"
            ),
            {
                "number": f"{MARKET_CODE}:{local_key}",
                "market": MARKET_CODE,
                "address": address,
                "owner": owner,
                "area": area,
                "frontage": frontage,
                "depth": depth,
                "value": value,
                "land_value": value,
                "vacant": vacant,
                "city_owned": local_key == "99900005",
                "polygon": _parcel_polygon(index),
                "srid": LOCAL_SRID,
            },
        )


async def _insert_supporting_records(session: AsyncSession) -> None:
    for local_key, document_id, sale_date, price in COMP_SALES:
        await session.execute(
            text(
                "INSERT INTO sale (parcel_number, document_id, document_type, sale_date, "
                "sale_price, source) VALUES (:number, :document_id, 'DEED', :sale_date, "
                ":price, :source)"
            ),
            {
                "number": f"{MARKET_CODE}:{local_key}",
                "document_id": document_id,
                "sale_date": sale_date,
                "price": price,
                "source": SOURCE,
            },
        )
    await session.execute(
        text(
            "INSERT INTO tax_status (parcel_number, is_delinquent, total_due, years_owed, source) "
            "VALUES (:number, TRUE, 22000, 4, :source)"
        ),
        {"number": f"{MARKET_CODE}:99900001", "source": SOURCE},
    )


async def _run() -> None:
    settings = get_settings()
    configure_logging(settings)
    logger = get_logger("e2e.seed")
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session:
            await _clear(session)
            await _insert_district(session)
            await _insert_parcels(session)
            await _insert_supporting_records(session)
            await session.commit()
            computed = await recompute_verdicts(session, PARCEL_NUMBERS)
            await session.commit()
        logger.info("e2e_seeded", parcels=len(PARCEL_NUMBERS), verdicts=computed)
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
