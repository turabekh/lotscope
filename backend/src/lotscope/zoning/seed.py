import asyncio
from typing import Any

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.logging import configure_logging, get_logger
from lotscope.zoning.models import ZoningStandard

TITLE_14_VERSION = "title14-quickguide-2026-02"
TITLE_14_SOURCE = (
    "Philadelphia Zoning Code Base Districts Quick Guide "
    "(Dept. of Planning & Development, Feb 2026): "
    "Table 14-701-1/-2 dimensional standards, Table 14-602-1 use tables"
)

_PROVISIONAL_VERSION = "title14-provisional-2024"
_PROVISIONAL_SOURCE = (
    "Provisional estimate — not yet transcribed from the official Title 14 tables; verify"
)

_SINGLE_FAMILY = ["single_family"]
_TWO_FAMILY = ["single_family", "two_family"]
_MULTI_FAMILY = ["single_family", "two_family", "multi_family"]
_RES_COMMERCIAL = ["single_family", "two_family", "multi_family", "commercial"]
_TWO_MULTI_COMMERCIAL = ["two_family", "multi_family", "commercial"]
_MULTI_COMMERCIAL = ["multi_family", "commercial"]
_COMMERCIAL = ["commercial"]
_INDUSTRIAL = ["commercial", "industrial"]
_IND_MIXED = ["multi_family", "commercial", "industrial"]

TITLE_14_STANDARDS: list[dict[str, Any]] = [
    {
        "code": "RSD-1",
        "permitted_uses": _SINGLE_FAMILY,
        "min_lot_area_sqft": 10000,
        "min_lot_width_ft": 75,
        "max_height_ft": 38,
        "max_units": 1,
        "max_occupancy_pct": 35,
        "front_setback_ft": 35,
        "rear_setback_ft": 30,
        "side_setback_ft": 15,
    },
    {
        "code": "RSD-2",
        "permitted_uses": _SINGLE_FAMILY,
        "min_lot_area_sqft": 7800,
        "min_lot_width_ft": 65,
        "max_height_ft": 38,
        "max_units": 1,
        "max_occupancy_pct": 35,
        "front_setback_ft": 35,
        "rear_setback_ft": 30,
        "side_setback_ft": 10,
    },
    {
        "code": "RSD-3",
        "permitted_uses": _SINGLE_FAMILY,
        "min_lot_area_sqft": 5000,
        "min_lot_width_ft": 50,
        "max_height_ft": 38,
        "max_units": 1,
        "max_occupancy_pct": 30,
        "front_setback_ft": 25,
        "rear_setback_ft": 25,
        "side_setback_ft": 7,
    },
    {
        "code": "RSA-1",
        "permitted_uses": _SINGLE_FAMILY,
        "min_lot_area_sqft": 5000,
        "min_lot_width_ft": 50,
        "max_height_ft": 38,
        "max_units": 1,
        "max_occupancy_pct": 30,
        "front_setback_ft": 25,
        "rear_setback_ft": 25,
        "side_setback_ft": 7,
    },
    {
        "code": "RSA-2",
        "permitted_uses": _SINGLE_FAMILY,
        "min_lot_area_sqft": 3150,
        "min_lot_width_ft": 35,
        "max_height_ft": 38,
        "max_units": 1,
        "max_occupancy_pct": 40,
        "front_setback_ft": 15,
        "rear_setback_ft": 20,
        "side_setback_ft": 6,
    },
    {
        "code": "RSA-3",
        "permitted_uses": _SINGLE_FAMILY,
        "min_lot_area_sqft": 2250,
        "min_lot_width_ft": 25,
        "max_height_ft": 38,
        "max_units": 1,
        "max_occupancy_pct": 50,
        "front_setback_ft": 8,
        "rear_setback_ft": 15,
        "side_setback_ft": 8,
    },
    {
        "code": "RSA-4",
        "permitted_uses": _SINGLE_FAMILY,
        "min_lot_area_sqft": 1620,
        "min_lot_width_ft": 18,
        "max_height_ft": 38,
        "max_units": 1,
        "max_occupancy_pct": 50,
        "front_setback_ft": 15,
        "rear_setback_ft": 20,
        "side_setback_ft": 6,
    },
    {
        "code": "RSA-5",
        "permitted_uses": _SINGLE_FAMILY,
        "min_lot_area_sqft": 1440,
        "min_lot_width_ft": 16,
        "max_height_ft": 38,
        "max_units": 1,
        "max_occupancy_pct": 75,
        "rear_setback_ft": 9,
        "side_setback_ft": 5,
    },
    {
        "code": "RTA-1",
        "permitted_uses": _TWO_FAMILY,
        "min_lot_area_sqft": 2250,
        "min_lot_width_ft": 25,
        "max_height_ft": 38,
        "max_units": 2,
        "max_occupancy_pct": 50,
        "front_setback_ft": 8,
        "rear_setback_ft": 15,
        "side_setback_ft": 8,
    },
    {
        "code": "RTA-2",
        "permitted_uses": _TWO_FAMILY,
        "min_lot_area_sqft": 1080,
        "min_lot_width_ft": 16,
        "max_height_ft": 35,
        "max_units": 2,
        "max_occupancy_pct": 75,
        "rear_setback_ft": 7,
        "side_setback_ft": 5,
    },
    {
        "code": "RM-1",
        "permitted_uses": _MULTI_FAMILY,
        "min_lot_area_sqft": 1440,
        "min_lot_width_ft": 16,
        "max_height_ft": 38,
        "max_occupancy_pct": 75,
        "rear_setback_ft": 9,
        "side_setback_ft": 5,
    },
    {
        "code": "RMX-1",
        "permitted_uses": _RES_COMMERCIAL,
        "max_occupancy_pct": 50,
    },
    {
        "code": "RMX-2",
        "permitted_uses": _RES_COMMERCIAL,
        "max_occupancy_pct": 75,
    },
    {
        "code": "RMX-3",
        "permitted_uses": _RES_COMMERCIAL,
        "max_occupancy_pct": 90,
        "front_setback_ft": 25,
        "rear_setback_ft": 25,
        "side_setback_ft": 8,
    },
    {
        "code": "CA-1",
        "permitted_uses": _COMMERCIAL,
        "min_lot_area_sqft": 5000,
        "max_height_ft": 38,
        "max_occupancy_pct": 60,
        "rear_setback_ft": 5,
        "side_setback_ft": 5,
    },
    {
        "code": "CA-2",
        "permitted_uses": _COMMERCIAL,
        "min_lot_area_sqft": 15000,
        "max_height_ft": 38,
        "max_occupancy_pct": 100,
    },
    {
        "code": "CMX-1",
        "permitted_uses": _RES_COMMERCIAL,
    },
    {
        "code": "CMX-2",
        "permitted_uses": _RES_COMMERCIAL,
        "max_height_ft": 38,
        "max_occupancy_pct": 75,
        "rear_setback_ft": 9,
        "side_setback_ft": 5,
    },
    {
        "code": "CMX-2.5",
        "permitted_uses": _RES_COMMERCIAL,
        "max_height_ft": 55,
        "max_occupancy_pct": 75,
        "rear_setback_ft": 9,
        "side_setback_ft": 5,
    },
    {
        "code": "CMX-3",
        "permitted_uses": _TWO_MULTI_COMMERCIAL,
        "max_occupancy_pct": 75,
        "side_setback_ft": 8,
    },
    {
        "code": "CMX-4",
        "permitted_uses": _MULTI_COMMERCIAL,
        "max_occupancy_pct": 90,
        "side_setback_ft": 8,
    },
    {
        "code": "CMX-5",
        "permitted_uses": _MULTI_COMMERCIAL,
        "max_occupancy_pct": 90,
        "side_setback_ft": 8,
    },
    {
        "code": "IRMX",
        "permitted_uses": _IND_MIXED,
        "max_height_ft": 60,
        "max_occupancy_pct": 75,
        "front_setback_ft": 0,
        "rear_setback_ft": 0,
        "side_setback_ft": 0,
    },
    {
        "code": "ICMX",
        "permitted_uses": _INDUSTRIAL,
        "max_height_ft": 60,
        "max_occupancy_pct": 100,
        "front_setback_ft": 0,
        "rear_setback_ft": 8,
        "side_setback_ft": 8,
    },
    {
        "code": "I-1",
        "permitted_uses": _INDUSTRIAL,
        "max_occupancy_pct": 100,
        "front_setback_ft": 0,
        "rear_setback_ft": 8,
        "side_setback_ft": 8,
    },
    {
        "code": "I-2",
        "permitted_uses": _INDUSTRIAL,
        "max_occupancy_pct": 100,
        "front_setback_ft": 0,
        "rear_setback_ft": 8,
        "side_setback_ft": 6,
    },
    {
        "code": "I-3",
        "permitted_uses": _INDUSTRIAL,
        "max_occupancy_pct": 100,
        "front_setback_ft": 0,
        "rear_setback_ft": 8,
        "side_setback_ft": 8,
    },
    {
        "code": "I-P",
        "permitted_uses": _INDUSTRIAL,
        "max_occupancy_pct": 100,
        "front_setback_ft": 0,
    },
    {
        "code": "RM-2",
        "permitted_uses": _MULTI_FAMILY,
        "max_height_ft": 38,
        "code_version": _PROVISIONAL_VERSION,
        "source": _PROVISIONAL_SOURCE,
    },
]

_DIMENSIONAL_FIELDS = (
    "min_lot_area_sqft",
    "min_lot_width_ft",
    "max_height_ft",
    "max_units",
    "max_occupancy_pct",
    "front_setback_ft",
    "rear_setback_ft",
    "side_setback_ft",
    "min_parking_spaces",
)
_UPDATE_COLUMNS = ("source", "permitted_uses", *_DIMENSIONAL_FIELDS)


def _row(entry: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "code": entry["code"],
        "code_version": entry.get("code_version", TITLE_14_VERSION),
        "source": entry.get("source", TITLE_14_SOURCE),
        "permitted_uses": entry["permitted_uses"],
    }
    for field_name in _DIMENSIONAL_FIELDS:
        row[field_name] = entry.get(field_name)
    return row


async def seed_zoning_standards(session: AsyncSession) -> int:
    rows = [_row(entry) for entry in TITLE_14_STANDARDS]
    statement = insert(ZoningStandard).values(rows)
    assignments: dict[str, Any] = {column: statement.excluded[column] for column in _UPDATE_COLUMNS}
    assignments["updated_at"] = func.now()
    statement = statement.on_conflict_do_update(
        constraint="uq_zoning_standard_code_version", set_=assignments
    )
    await session.execute(statement)
    return len(rows)


async def _run() -> None:
    settings = get_settings()
    configure_logging(settings)
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session:
            count = await seed_zoning_standards(session)
            await session.commit()
            get_logger("zoning.seed").info("seeded_zoning_standards", count=count)
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
