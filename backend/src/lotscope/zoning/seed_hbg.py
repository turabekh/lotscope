from datetime import date
from typing import Any

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.zoning.models import ZoningStandard

HBG_MARKET = "hbg"
HBG_CODE_VERSION = "hbg-provisional-2026"
HBG_SOURCE = (
    "Harrisburg Zoning Code § 7-307.3A Development Standards (Attachment 1, 2017-12-01); "
    "permitted uses provisional from § 7-305.4 district purposes, pending the § 7-305.7 use table"
)
_EFFECTIVE = date(2017, 12, 1)

HBG_STANDARDS: tuple[dict[str, Any], ...] = (
    {
        "code": "OSR",
        "min_lot_area_sqft": 2000,
        "min_lot_width_ft": 20,
        "max_height_ft": 45,
        "front_setback_ft": 15,
        "rear_setback_ft": 15,
        "side_setback_ft": 5,
        "max_occupancy_pct": 30,
        "dimensional": {"district_name": "Open Space Recreation"},
    },
    {
        "code": "RL",
        "min_lot_area_sqft": 5000,
        "min_lot_width_ft": 50,
        "max_height_ft": 36,
        "front_setback_ft": 20,
        "rear_setback_ft": 15,
        "side_setback_ft": 5,
        "max_occupancy_pct": 50,
        "dimensional": {
            "district_name": "Low Density Residential",
            "density_du_per_acre": "4-8",
            "nonresidential_min_lot_area_sqft": 8000,
            "nonresidential_min_lot_width_ft": 80,
            "front_setback_note": "minimum of 20 feet or conform to existing prevailing setback",
            "height_note": "36 ft max; principal building width no greater than 20% of "
            "prevailing width on block",
        },
    },
    {
        "code": "RM",
        "min_lot_area_sqft": 1500,
        "lot_area_per_unit_sqft": 1500,
        "min_lot_width_ft": 20,
        "max_height_ft": 45,
        "front_setback_ft": 5,
        "rear_setback_ft": 10,
        "side_setback_ft": 4,
        "max_occupancy_pct": 70,
        "dimensional": {
            "district_name": "Medium Density Residential",
            "density_du_per_acre": "8-20",
            "nonresidential_min_lot_area_sqft": 3000,
            "front_setback_note": "conform to prevailing block setback, minimum 5 feet where "
            "none prevailing",
            "side_setback_note": "4 feet each except 0 feet at the shared lot line of lawfully "
            "attached dwellings",
        },
    },
    {
        "code": "CN",
        "min_lot_area_sqft": 1200,
        "lot_area_per_unit_sqft": 1200,
        "min_lot_width_ft": 20,
        "max_height_ft": 75,
        "front_setback_ft": 0,
        "rear_setback_ft": 5,
        "side_setback_ft": 4,
        "max_occupancy_pct": 95,
        "dimensional": {
            "district_name": "Commercial Neighborhood",
            "nonresidential_min_lot_area_sqft": 2000,
            "front_setback_note": "conform to prevailing setback; MAXIMUM 5 feet (build-to) where "
            "none prevailing — no minimum required",
            "side_setback_note": "4 feet each except 0 feet at the shared lot line of lawfully "
            "attached structures",
        },
    },
    {
        "code": "CG",
        "min_lot_area_sqft": 3000,
        "min_lot_width_ft": 20,
        "max_height_ft": 100,
        "front_setback_ft": 5,
        "rear_setback_ft": 5,
        "side_setback_ft": 5,
        "max_occupancy_pct": 95,
        "dimensional": {
            "district_name": "Commercial General",
            "front_setback_note": "conform to prevailing setback, minimum 5 feet where none "
            "prevailing",
            "side_setback_note": "5 feet each except 0 feet at the shared lot line of lawfully "
            "attached structures",
        },
    },
    {
        "code": "DC",
        "min_lot_area_sqft": 1200,
        "min_lot_width_ft": 20,
        "max_height_ft": None,
        "front_setback_ft": 5,
        "rear_setback_ft": 0,
        "side_setback_ft": 0,
        "max_occupancy_pct": 100,
        "dimensional": {
            "district_name": "Downtown Center",
            "height_note": "45 feet minimum, no maximum",
            "rear_setback_note": "No minimum",
            "side_setback_note": "No minimum",
            "front_setback_note": "conform to prevailing setback, minimum 5 feet where none "
            "prevailing",
        },
    },
    {
        "code": "RF",
        "min_lot_area_sqft": 2000,
        "min_lot_width_ft": None,
        "max_height_ft": 45,
        "front_setback_ft": None,
        "rear_setback_ft": None,
        "side_setback_ft": 10,
        "max_occupancy_pct": 75,
        "dimensional": {
            "district_name": "Riverfront",
            "min_lot_width_note": "20 feet south of Reily Street; 50 feet north of Reily Street",
            "front_setback_note": "50 feet along Front Street north of Reily Street; 15 feet "
            "along Front Street south of Reily Street or conforming to existing; State Street "
            "setbacks conform to existing",
            "rear_setback_note": "15 feet for parcels along Front Street; 5 feet for parcels "
            "along State Street",
            "height_note": "36 feet minimum, 45 feet maximum",
        },
    },
    {
        "code": "INS",
        "min_lot_area_sqft": 5000,
        "min_lot_width_ft": 50,
        "max_height_ft": 100,
        "front_setback_ft": 20,
        "rear_setback_ft": 20,
        "side_setback_ft": 20,
        "max_occupancy_pct": 75,
        "dimensional": {
            "district_name": "Institutional",
            "front_setback_note": "20 feet or conform to the prevailing setback in the block",
        },
    },
    {
        "code": "IND",
        "min_lot_area_sqft": 5000,
        "min_lot_width_ft": 30,
        "max_height_ft": None,
        "front_setback_ft": 10,
        "rear_setback_ft": 5,
        "side_setback_ft": 5,
        "max_occupancy_pct": 75,
        "dimensional": {"district_name": "Industrial", "height_note": "no maximum"},
    },
)

_PERMITTED_USES: dict[str, list[str]] = {
    "OSR": ["parks", "recreation"],
    "RL": ["single_family"],
    "RM": ["single_family", "two_family", "multi_family"],
    "CN": ["single_family", "two_family", "multi_family", "commercial"],
    "CG": ["multi_family", "commercial"],
    "DC": ["multi_family", "commercial"],
    "RF": ["single_family", "two_family"],
    "INS": ["institutional", "civic", "commercial"],
    "IND": ["commercial", "industrial"],
}

_COLUMNS = (
    "min_lot_area_sqft",
    "min_lot_width_ft",
    "max_height_ft",
    "lot_area_per_unit_sqft",
    "max_occupancy_pct",
    "front_setback_ft",
    "rear_setback_ft",
    "side_setback_ft",
)
_UPDATE = ("source", "effective_date", "dimensional", "permitted_uses", *_COLUMNS)


def _row(entry: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "market_code": HBG_MARKET,
        "code": entry["code"],
        "code_version": HBG_CODE_VERSION,
        "source": HBG_SOURCE,
        "effective_date": _EFFECTIVE,
        "permitted_uses": _PERMITTED_USES.get(entry["code"], []),
        "requires_master_plan": False,
        "dimensional": entry.get("dimensional", {}),
    }
    for column in _COLUMNS:
        row[column] = entry.get(column)
    return row


async def seed_hbg_zoning_standards(session: AsyncSession) -> int:
    rows = [_row(entry) for entry in HBG_STANDARDS]
    statement = insert(ZoningStandard).values(rows)
    assignments: dict[str, Any] = {column: statement.excluded[column] for column in _UPDATE}
    assignments["updated_at"] = func.now()
    statement = statement.on_conflict_do_update(
        constraint="uq_zoning_standard_market_code_version", set_=assignments
    )
    await session.execute(statement)
    return len(rows)
