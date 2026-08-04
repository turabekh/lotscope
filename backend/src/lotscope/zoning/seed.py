import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.logging import configure_logging, get_logger
from lotscope.zoning.models import ZoningStandard
from lotscope.zoning.seed_hbg import seed_hbg_zoning_standards
from lotscope.zoning.seed_pgh import seed_pgh_zoning_standards
from lotscope.zoning.seed_wlm import seed_wlm_zoning_standards

TITLE_14_VERSION = "title14-quickguide-2026-02"
TITLE_14_SOURCE = (
    "Philadelphia Zoning Code Base Districts Quick Guide "
    "(Dept. of Planning & Development, Feb 2026): "
    "Table 14-701-1/-2 dimensional standards, Table 14-602-1 use tables"
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
_SP_INSTITUTIONAL = ["institutional", "civic", "commercial"]
_SP_PARKS = ["parks", "recreation"]
_SP_ENTERTAINMENT = ["entertainment", "commercial", "multi_family"]
_SP_STADIUM = ["stadium", "commercial"]
_SP_AIRPORT = ["airport", "commercial", "industrial"]

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
        "lot_area_per_unit_sqft": 480,
        "max_occupancy_pct": 75,
        "rear_setback_ft": 9,
        "side_setback_ft": 5,
    },
    {
        "code": "RMX-1",
        "permitted_uses": _RES_COMMERCIAL,
        "max_occupancy_pct": 50,
        "requires_master_plan": True,
    },
    {
        "code": "RMX-2",
        "permitted_uses": _RES_COMMERCIAL,
        "max_occupancy_pct": 75,
        "requires_master_plan": True,
    },
    {
        "code": "RMX-3",
        "permitted_uses": _RES_COMMERCIAL,
        "max_floor_area_ratio_pct": 500,
        "max_occupancy_pct": 90,
        "front_setback_ft": 25,
        "rear_setback_ft": 25,
        "side_setback_ft": 8,
        "requires_master_plan": True,
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
        "lot_area_per_unit_sqft": 480,
        "max_occupancy_pct": 75,
        "rear_setback_ft": 9,
        "side_setback_ft": 5,
    },
    {
        "code": "CMX-2.5",
        "permitted_uses": _RES_COMMERCIAL,
        "max_height_ft": 55,
        "lot_area_per_unit_sqft": 360,
        "max_occupancy_pct": 75,
        "rear_setback_ft": 9,
        "side_setback_ft": 5,
    },
    {
        "code": "CMX-3",
        "permitted_uses": _TWO_MULTI_COMMERCIAL,
        "max_floor_area_ratio_pct": 500,
        "max_occupancy_pct": 75,
        "side_setback_ft": 8,
    },
    {
        "code": "CMX-4",
        "permitted_uses": _MULTI_COMMERCIAL,
        "max_floor_area_ratio_pct": 500,
        "max_occupancy_pct": 90,
        "side_setback_ft": 8,
    },
    {
        "code": "CMX-5",
        "permitted_uses": _MULTI_COMMERCIAL,
        "max_floor_area_ratio_pct": 1200,
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
        "code": "RSA-6",
        "permitted_uses": _SINGLE_FAMILY,
        "min_lot_area_sqft": 700,
        "min_lot_width_ft": 14,
        "max_height_ft": 25,
        "max_units": 1,
        "max_occupancy_pct": 80,
        "rear_setback_ft": 7,
        "side_setback_ft": 5,
    },
    {
        "code": "RM-2",
        "permitted_uses": _MULTI_FAMILY,
        "min_lot_area_sqft": 15000,
        "min_lot_width_ft": 50,
        "max_floor_area_ratio_pct": 70,
    },
    {
        "code": "RM-3",
        "permitted_uses": _MULTI_FAMILY,
        "min_lot_area_sqft": 10000,
        "min_lot_width_ft": 50,
        "max_floor_area_ratio_pct": 150,
        "max_occupancy_pct": 50,
        "front_setback_ft": 20,
        "rear_setback_ft": 20,
    },
    {
        "code": "RM-4",
        "permitted_uses": _MULTI_FAMILY,
        "min_lot_area_sqft": 2500,
        "min_lot_width_ft": 20,
        "max_floor_area_ratio_pct": 350,
        "max_occupancy_pct": 75,
        "rear_setback_ft": 5,
        "side_setback_ft": 5,
    },
    {
        "code": "SP-INS",
        "requires_master_plan": True,
        "permitted_uses": _SP_INSTITUTIONAL,
        "max_occupancy_pct": 70,
    },
    {
        "code": "SP-CIV",
        "requires_master_plan": True,
        "permitted_uses": _SP_INSTITUTIONAL,
        "max_occupancy_pct": 80,
        "side_setback_ft": 8,
    },
    {
        "code": "SP-PO-A",
        "requires_master_plan": True,
        "permitted_uses": _SP_PARKS,
    },
    {
        "code": "SP-PO-P",
        "requires_master_plan": True,
        "permitted_uses": _SP_PARKS,
    },
    {
        "code": "SP-ENT",
        "requires_master_plan": True,
        "permitted_uses": _SP_ENTERTAINMENT,
        "max_height_ft": 300,
    },
    {
        "code": "SP-STA",
        "requires_master_plan": True,
        "permitted_uses": _SP_STADIUM,
    },
    {
        "code": "SP-AIR",
        "requires_master_plan": True,
        "permitted_uses": _SP_AIRPORT,
        "max_occupancy_pct": 70,
        "side_setback_ft": 6,
    },
]

_DIMENSIONAL_FIELDS = (
    "min_lot_area_sqft",
    "min_lot_width_ft",
    "max_height_ft",
    "max_units",
    "lot_area_per_unit_sqft",
    "max_floor_area_ratio_pct",
    "max_occupancy_pct",
    "front_setback_ft",
    "rear_setback_ft",
    "side_setback_ft",
)
_UPDATE_COLUMNS = (
    "source",
    "permitted_uses",
    "requires_master_plan",
    "field_dispositions",
    *_DIMENSIONAL_FIELDS,
)

_UNREGULATED = {"disposition": "unregulated"}


def _conditional(note: str) -> dict[str, str]:
    return {"disposition": "conditional", "note": note}


_NO_LOT_MINIMUMS = {
    "min_lot_area_sqft": _UNREGULATED,
    "min_lot_width_ft": _UNREGULATED,
}
_FAR_GOVERNED_DENSITY = {
    "disposition": "unregulated",
    "note": "unit yield is governed by the floor-area ratio rather than a lot-area-per-unit rule",
}
_FAR_GOVERNED_HEIGHT = {
    "min_lot_area_sqft": _UNREGULATED,
    "min_lot_width_ft": _UNREGULATED,
    "max_height_ft": {
        "disposition": "unregulated",
        "note": (
            "building size is governed by the floor-area ratio and the bonus provisions instead"
        ),
    },
    "max_units": _FAR_GOVERNED_DENSITY,
    "lot_area_per_unit_sqft": _FAR_GOVERNED_DENSITY,
}
_MASTER_PLAN_DIMENSION = _conditional(
    "set through the required master-plan approval rather than by a by-right district standard"
)
_MASTER_PLAN_DIMENSIONS = {
    "min_lot_area_sqft": _UNREGULATED,
    "min_lot_width_ft": _UNREGULATED,
    "max_height_ft": _MASTER_PLAN_DIMENSION,
    "max_units": _MASTER_PLAN_DIMENSION,
    "lot_area_per_unit_sqft": _MASTER_PLAN_DIMENSION,
}
_INDUSTRIAL_HEIGHT = _conditional(
    "60 ft. where the lot abuts a Residential or SP-PO district; otherwise no height limit"
)
_CMX1_MATCHES_NEIGHBOURS = _conditional(
    "Occupied area, building dimensions, and height follow the requirements of the adjacent "
    "residential districts, so they vary by location rather than by district"
)

PHL_FIELD_DISPOSITIONS: dict[str, dict[str, dict[str, str]]] = {
    "CMX-1": {
        "min_lot_area_sqft": _CMX1_MATCHES_NEIGHBOURS,
        "min_lot_width_ft": _CMX1_MATCHES_NEIGHBOURS,
        "max_height_ft": _CMX1_MATCHES_NEIGHBOURS,
    },
    "CMX-2": _NO_LOT_MINIMUMS,
    "CMX-2.5": _NO_LOT_MINIMUMS,
    "CMX-3": _FAR_GOVERNED_HEIGHT,
    "CMX-4": _FAR_GOVERNED_HEIGHT,
    "CMX-5": _FAR_GOVERNED_HEIGHT,
    "IRMX": _NO_LOT_MINIMUMS,
    "ICMX": _NO_LOT_MINIMUMS,
    "I-1": {**_NO_LOT_MINIMUMS, "max_height_ft": _INDUSTRIAL_HEIGHT},
    "I-2": {**_NO_LOT_MINIMUMS, "max_height_ft": _INDUSTRIAL_HEIGHT},
    "I-3": {**_NO_LOT_MINIMUMS, "max_height_ft": _INDUSTRIAL_HEIGHT},
    "RMX-1": _MASTER_PLAN_DIMENSIONS,
    "RMX-2": _MASTER_PLAN_DIMENSIONS,
    "RMX-3": _MASTER_PLAN_DIMENSIONS,
    "CA-1": {"min_lot_width_ft": _UNREGULATED},
    "CA-2": {"min_lot_width_ft": _UNREGULATED},
    "RM-2": {
        "max_height_ft": _conditional(
            "expressed as a floor-area ratio (70% of lot area) rather than a fixed height"
        )
    },
    "RM-3": {
        "max_height_ft": _conditional(
            "expressed as a floor-area ratio (150% of lot area) rather than a fixed height"
        )
    },
    "RM-4": {
        "max_height_ft": _conditional(
            "expressed as a floor-area ratio (350% of lot area) rather than a fixed height"
        )
    },
}


def _row(entry: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "market_code": entry.get("market_code", "phl"),
        "code": entry["code"],
        "code_version": entry.get("code_version", TITLE_14_VERSION),
        "source": entry.get("source", TITLE_14_SOURCE),
        "permitted_uses": entry["permitted_uses"],
        "requires_master_plan": entry.get("requires_master_plan", False),
        "field_dispositions": PHL_FIELD_DISPOSITIONS.get(entry["code"], {})
        if entry.get("market_code", "phl") == "phl"
        else {},
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
        constraint="uq_zoning_standard_market_code_version", set_=assignments
    )
    await session.execute(statement)
    return len(rows)


_MARKET_SEEDERS: dict[str, Callable[[AsyncSession], Awaitable[int]]] = {
    "phl": seed_zoning_standards,
    "hbg": seed_hbg_zoning_standards,
    "pgh": seed_pgh_zoning_standards,
    "wlm": seed_wlm_zoning_standards,
}


async def seed_all_zoning_standards(session: AsyncSession) -> dict[str, int]:
    return {market: await seeder(session) for market, seeder in _MARKET_SEEDERS.items()}


async def _run() -> None:
    settings = get_settings()
    configure_logging(settings)
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session:
            seeded = await seed_all_zoning_standards(session)
            await session.commit()
            get_logger("zoning.seed").info("seeded_zoning_standards", **seeded)
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
