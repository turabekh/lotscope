import asyncio
import json
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.zoning.seed import TITLE_14_STANDARDS
from lotscope.zoning.seed_overlay import TITLE_14_OVERLAY_STANDARDS

TABLE_14_701_1_MIN_LOT_AREA = {
    "RSD-1": 10_000,
    "RSD-2": 7_800,
    "RSD-3": 5_000,
    "RSA-1": 5_000,
    "RSA-2": 3_150,
    "RSA-3": 2_250,
    "RSA-4": 1_620,
    "RSA-5": 960,
    "RSA-6": 700,
    "RTA-1": 2_250,
    "RTA-2": 1_080,
}

TABLE_14_701_2_MIN_LOT_AREA = {
    "RM-1": 1_440,
    "RM-2": 15_000,
    "RM-3": 10_000,
    "RM-4": 2_500,
}

TABLE_14_701_4_MAX_FLOOR_AREA_PCT = {
    "IRMX": 500,
    "ICMX": 500,
    "I-1": 500,
    "I-2": 500,
    "I-3": 500,
}

_PROVISION_SQL = text(
    "SELECT regexp_replace(coalesce(text, ''), '\\s+', ' ', 'g') AS body "
    "FROM code_provision WHERE market_code = :market_code AND cite = :cite"
)

_OVERLAY_SECTION_SQL = text(
    "SELECT count(*) FROM zoning_overlay "
    "WHERE market_code = :market_code AND code_section = :code_section"
)


@dataclass(frozen=True)
class Divergence:
    scope: str
    subject: str
    field: str
    expected: str
    actual: str


def _seeded(field: str) -> dict[str, float]:
    return {
        entry["code"]: entry[field] for entry in TITLE_14_STANDARDS if entry.get(field) is not None
    }


def _check_printed_table(
    table_label: str, field: str, printed: Mapping[str, float]
) -> list[Divergence]:
    seeded = _seeded(field)
    divergences: list[Divergence] = []
    for code, expected in printed.items():
        actual = seeded.get(code)
        if actual is None:
            divergences.append(
                Divergence(table_label, code, field, str(expected), "absent from seed")
            )
        elif float(actual) != float(expected):
            divergences.append(Divergence(table_label, code, field, str(expected), str(actual)))
    return divergences


def _numerals(body: str) -> set[str]:
    return {match.replace(",", "") for match in re.findall(r"\d[\d,]*", body)}


async def _check_overlay_sections(session: AsyncSession, market_code: str) -> list[Divergence]:
    divergences: list[Divergence] = []
    for entry in TITLE_14_OVERLAY_STANDARDS:
        citation = entry["citation"]
        body = await session.scalar(_PROVISION_SQL, {"market_code": market_code, "cite": citation})
        if not body:
            divergences.append(
                Divergence("overlay", citation, entry["field"], str(entry["value"]), "cite absent")
            )
            continue
        if str(int(entry["value"])) not in _numerals(body):
            divergences.append(
                Divergence(
                    "overlay", citation, entry["field"], str(entry["value"]), "value not in cite"
                )
            )
        polygons = await session.scalar(
            _OVERLAY_SECTION_SQL,
            {"market_code": market_code, "code_section": entry["code_section"]},
        )
        if not polygons:
            divergences.append(
                Divergence(
                    "overlay",
                    entry["code_section"],
                    "geometry",
                    ">=1 polygon",
                    "no zoning_overlay row",
                )
            )
    return divergences


async def verify_zoning_standards(session: AsyncSession, market_code: str) -> list[Divergence]:
    divergences: list[Divergence] = []
    divergences += _check_printed_table(
        "table-14-701-1", "min_lot_area_sqft", TABLE_14_701_1_MIN_LOT_AREA
    )
    divergences += _check_printed_table(
        "table-14-701-2", "min_lot_area_sqft", TABLE_14_701_2_MIN_LOT_AREA
    )
    divergences += _check_printed_table(
        "table-14-701-4", "max_floor_area_ratio_pct", TABLE_14_701_4_MAX_FLOOR_AREA_PCT
    )
    divergences += await _check_overlay_sections(session, market_code)
    return divergences


async def main() -> int:
    settings = get_settings()
    session_factory = create_session_factory(create_engine(settings))
    async with session_factory() as session:
        divergences = await verify_zoning_standards(session, "phl")
    for divergence in divergences:
        print(
            json.dumps(
                {
                    "scope": divergence.scope,
                    "subject": divergence.subject,
                    "field": divergence.field,
                    "expected": divergence.expected,
                    "actual": divergence.actual,
                }
            )
        )
    if divergences:
        print(f"FAIL {len(divergences)} divergence(s)")
        return 1
    print("OK zoning standards match the printed tables and the cited overlay sections")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
