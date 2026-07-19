from typing import Any

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.zoning.models import ZoningStandard

WLM_MARKET = "wlm"
WLM_CODE_VERSION = "wlm-provisional-2026"
WLM_SOURCE = (
    "Wilmington City Code Ch. 48 (Zoning), Art. IV-VIII "
    "(res. 48-151/152, comm. 48-211/212, mfg. 48-261/262, open 48-286, waterfront 48-353/355)"
)

WLM_STANDARDS: tuple[dict[str, Any], ...] = (
    {
        "code": "R-1",
        "min_lot_area_sqft": 6500,
        "min_lot_width_ft": 60,
        "max_height_ft": 40,
        "max_units": 1,
        "permitted_uses": ["Single-family detached"],
    },
    {
        "code": "R-2",
        "min_lot_area_sqft": 4000,
        "min_lot_width_ft": 40,
        "max_height_ft": 40,
        "max_units": 2,
        "permitted_uses": ["Single-family and two-family, semi-detached"],
    },
    {
        "code": "R-2A",
        "min_lot_width_ft": 40,
        "max_height_ft": 40,
        "permitted_uses": ["Low-rise apartment house"],
    },
    {
        "code": "R-3",
        "min_lot_area_sqft": 1600,
        "min_lot_width_ft": 16,
        "max_height_ft": 40,
        "max_units": 1,
        "permitted_uses": ["Single-family attached (rowhouse)"],
    },
    {
        "code": "R-4",
        "min_lot_area_sqft": 1280,
        "min_lot_width_ft": 16,
        "max_height_ft": 40,
        "permitted_uses": ["Rowhouse and apartment house"],
    },
    {
        "code": "R-5A",
        "min_lot_area_sqft": 43560,
        "max_height_ft": 40,
        "permitted_uses": ["Garden apartments"],
    },
    {
        "code": "R-5A1",
        "max_height_ft": 60,
        "max_floor_area_ratio_pct": 200,
        "permitted_uses": ["Mid-rise multi-family"],
    },
    {
        "code": "R-5B",
        "max_height_ft": 180,
        "max_floor_area_ratio_pct": 350,
        "permitted_uses": ["High-rise multi-family"],
    },
    {
        "code": "R-5C",
        "max_floor_area_ratio_pct": 600,
        "permitted_uses": ["High-density multi-family"],
    },
    {"code": "C-1", "max_height_ft": 47, "permitted_uses": ["Neighborhood retail / office"]},
    {
        "code": "C-1A",
        "max_height_ft": 47,
        "permitted_uses": ["Neighborhood commercial (restricted)"],
    },
    {"code": "C-2", "max_height_ft": 180, "permitted_uses": ["Secondary commercial center"]},
    {
        "code": "C-2A",
        "max_floor_area_ratio_pct": 100,
        "permitted_uses": ["Low-intensity office / buffer"],
    },
    {"code": "C-3", "max_height_ft": 180, "permitted_uses": ["Central retail district"]},
    {
        "code": "C-4",
        "max_floor_area_ratio_pct": 2000,
        "permitted_uses": ["Central office (high density)"],
    },
    {"code": "C-5", "max_height_ft": 55, "permitted_uses": ["Heavy commercial / warehousing"]},
    {
        "code": "C-6",
        "max_floor_area_ratio_pct": 1000,
        "permitted_uses": ["Special commercial arterial"],
    },
    {
        "code": "M-1",
        "max_height_ft": 55,
        "max_floor_area_ratio_pct": 200,
        "permitted_uses": ["Light manufacturing / industrial"],
    },
    {
        "code": "M-2",
        "max_height_ft": 90,
        "max_floor_area_ratio_pct": 300,
        "permitted_uses": ["Heavy manufacturing / industrial"],
    },
    {"code": "W-1", "max_height_ft": 72, "permitted_uses": ["Waterfront industrial / port"]},
    {"code": "W-2", "max_height_ft": 72, "permitted_uses": ["Waterfront commercial / industrial"]},
    {"code": "W-3", "max_height_ft": 72, "permitted_uses": ["Waterfront mixed-use"]},
    {"code": "W-4", "max_height_ft": 72, "permitted_uses": ["Waterfront residential / commercial"]},
    {
        "code": "O",
        "max_height_ft": 35,
        "permitted_uses": ["Public parks / open space / recreation"],
    },
)


async def seed_wlm_zoning_standards(session: AsyncSession) -> int:
    count = 0
    for row in WLM_STANDARDS:
        values = {
            "market_code": WLM_MARKET,
            "code_version": WLM_CODE_VERSION,
            "source": WLM_SOURCE,
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
