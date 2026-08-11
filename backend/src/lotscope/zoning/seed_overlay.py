from typing import Any

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.zoning.models import OverlayStandard

OVERLAY_VERSION = "title14-overlay-2026-08"

TITLE_14_OVERLAY_STANDARDS: list[dict[str, Any]] = [
    {
        "code_section": "14-514",
        "overlay_code": "/FNE",
        "district_code": "RSA-5",
        "field": "min_lot_area_sqft",
        "value": 1440,
        "citation": "14-514(5)(a)",
    },
    {
        "code_section": "14-515",
        "overlay_code": "/NE",
        "district_code": "RSA-5",
        "field": "min_lot_area_sqft",
        "value": 1440,
        "citation": "14-515(2)(c)(.1)",
    },
    {
        "code_section": "14-520",
        "overlay_code": "/NDO",
        "district_code": "RSA-5",
        "field": "min_lot_area_sqft",
        "value": 1440,
        "citation": "14-520(4)(a)",
    },
    {
        "code_section": "14-524",
        "overlay_code": "/FDO",
        "district_code": "RSA-5",
        "field": "min_lot_area_sqft",
        "value": 1440,
        "citation": "14-524(2)(a)",
    },
    {
        "code_section": "14-530",
        "overlay_code": "/EDO",
        "district_code": "RSA-5",
        "field": "min_lot_area_sqft",
        "value": 1440,
        "citation": "14-530(2)",
    },
    {
        "code_section": "14-548",
        "overlay_code": "/SIX",
        "district_code": "RSA-5",
        "field": "min_lot_area_sqft",
        "value": 1440,
        "citation": "14-548(3)(a)(.3)",
    },
]

_UPDATE_COLUMNS = ("overlay_code", "value", "citation")


def _row(entry: dict[str, Any]) -> dict[str, Any]:
    return {**entry, "market_code": "phl", "code_version": OVERLAY_VERSION}


async def seed_overlay_standards(session: AsyncSession) -> int:
    rows = [_row(entry) for entry in TITLE_14_OVERLAY_STANDARDS]
    statement = insert(OverlayStandard).values(rows)
    assignments: dict[str, Any] = {column: statement.excluded[column] for column in _UPDATE_COLUMNS}
    assignments["updated_at"] = func.now()
    statement = statement.on_conflict_do_update(
        constraint="uq_overlay_standard_scope", set_=assignments
    )
    await session.execute(statement)
    return len(rows)
