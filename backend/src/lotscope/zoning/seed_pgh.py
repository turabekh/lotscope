from datetime import date
from typing import Any

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.zoning.models import ZoningStandard

PGH_MARKET = "pgh"
PGH_CODE_VERSION = "pgh-provisional-2026"
PGH_SOURCE = "Pittsburgh Zoning Code, Title Nine § 903.03 (Development Subdistricts)"
_EFFECTIVE = date(2025, 5, 7)

# Residential Site Development Standards by density subdistrict (§ 903.03), verbatim per-page.
# Each density states one column for R1D/R1A/R2/R3 and a separate column for RM.
# Fields: (min_lot, front, rear, side_interior, height). min_lot None = unconfirmed (NULL).
_R1_COLUMN: dict[str, dict[str, Any]] = {
    "VL": {"lot": 6000, "front": 30, "rear": 30, "side": 5, "height": 40},
    "L": {"lot": 3000, "front": 30, "rear": 30, "side": 5, "height": 40},
    "M": {"lot": 2400, "front": 30, "rear": 30, "side": 5, "height": 40},
    "H": {"lot": 1200, "front": 15, "rear": 15, "side": 5, "height": 40},
    "VH": {"lot": None, "front": 5, "rear": 15, "side": 5, "height": 40},
}
_RM_COLUMN: dict[str, dict[str, Any]] = {
    "VL": {"lot": 6000, "front": 30, "rear": 30, "side": 30, "height": 40},
    "L": {"lot": 3000, "front": 25, "rear": 25, "side": 25, "height": 40},
    "M": {"lot": 2400, "front": 25, "rear": 25, "side": 10, "height": 55},
    "H": {"lot": 1200, "front": 25, "rear": 25, "side": 10, "height": 85},
    "VH": {"lot": None, "front": 25, "rear": 25, "side": 10, "height": 180},
}
_DISTRICT_NAME: dict[str, str] = {
    "R1D": "Single-Unit Detached Residential",
    "R1A": "Single-Unit Attached Residential",
    "R2": "Two-Unit Residential",
    "R3": "Three-Unit Residential",
    "RM": "Multi-Unit Residential",
}
_RESIDENTIAL_CODES: tuple[str, ...] = (
    "R1D-VL", "R1D-L", "R1D-M", "R1D-H", "R1D-VH",
    "R1A-M", "R1A-H", "R1A-VH",
    "R2-L", "R2-M", "R2-H", "R2-VH",
    "R3-L", "R3-M",
    "RM-VL", "RM-M", "RM-H", "RM-VH",
)


def _residential_standard(full_code: str) -> dict[str, Any]:
    base, density = full_code.rsplit("-", 1)
    column = _RM_COLUMN if base == "RM" else _R1_COLUMN
    values = column[density]
    return {
        "code": full_code,
        "min_lot_area_sqft": values["lot"],
        "front_setback_ft": values["front"],
        "rear_setback_ft": values["rear"],
        "side_setback_ft": values["side"],
        "max_height_ft": values["height"],
        "dimensional": {
            "district_name": _DISTRICT_NAME[base],
            "density_subdistrict": density,
            "max_height_stories": {40: 3, 55: 4, 85: 9}.get(values["height"]),
            "note": "Setback shown is the minimum interior sideyard; other yards vary — see § 903.03.",
        },
    }


PGH_STANDARDS: tuple[dict[str, Any], ...] = tuple(
    _residential_standard(code) for code in _RESIDENTIAL_CODES
)


async def seed_pgh_zoning_standards(session: AsyncSession) -> int:
    count = 0
    for row in PGH_STANDARDS:
        values = {
            "market_code": PGH_MARKET,
            "code_version": PGH_CODE_VERSION,
            "source": PGH_SOURCE,
            "effective_date": _EFFECTIVE,
            "updated_at": func.now(),
            **row,
        }
        stmt = insert(ZoningStandard).values(**values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_zoning_standard_market_code_version",
            set_={k: values[k] for k in row if k != "code"},
        )
        await session.execute(stmt)
        count += 1
    return count
