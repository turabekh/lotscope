import asyncio
from typing import Any

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.logging import configure_logging, get_logger
from lotscope.zoning.models import ZoningStandard

TITLE_14_VERSION = "title14-provisional-2024"
TITLE_14_SOURCE = "Philadelphia Code Title 14 (provisional values — verify against official text)"

_RESIDENTIAL = ["single_family"]
_MULTI_FAMILY = ["single_family", "two_family", "multi_family"]
_MIXED_USE = ["commercial", "multi_family"]

TITLE_14_STANDARDS: list[dict[str, Any]] = [
    {
        "code": "RSA-5",
        "permitted_uses": _RESIDENTIAL,
        "min_lot_area_sqft": 1440,
        "min_lot_width_ft": 16,
        "max_height_ft": 38,
        "max_units": 1,
    },
    {
        "code": "RSA-3",
        "permitted_uses": _RESIDENTIAL,
        "min_lot_area_sqft": 2160,
        "min_lot_width_ft": 18,
        "max_height_ft": 38,
        "max_units": 1,
    },
    {
        "code": "RSA-2",
        "permitted_uses": _RESIDENTIAL,
        "min_lot_area_sqft": 2880,
        "max_height_ft": 38,
        "max_units": 1,
    },
    {
        "code": "RSA-1",
        "permitted_uses": _RESIDENTIAL,
        "max_height_ft": 38,
        "max_units": 1,
    },
    {
        "code": "RM-1",
        "permitted_uses": _MULTI_FAMILY,
        "min_lot_area_sqft": 1440,
        "min_lot_width_ft": 16,
        "max_height_ft": 38,
    },
    {
        "code": "RM-2",
        "permitted_uses": _MULTI_FAMILY,
        "max_height_ft": 38,
    },
    {
        "code": "CMX-1",
        "permitted_uses": _MIXED_USE,
        "max_height_ft": 38,
    },
    {
        "code": "CMX-2",
        "permitted_uses": _MIXED_USE,
        "max_height_ft": 38,
    },
    {
        "code": "CMX-2.5",
        "permitted_uses": _MIXED_USE,
        "max_height_ft": 55,
    },
    {
        "code": "CMX-3",
        "permitted_uses": _MIXED_USE,
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
        "code_version": TITLE_14_VERSION,
        "source": TITLE_14_SOURCE,
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
