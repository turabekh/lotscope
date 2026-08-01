from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.goldset.schemas import ExpectedFacts, GoldCase, GoldCategory

_BASE = (
    "SELECT p.parcel_number FROM parcel p "
    "WHERE p.market_code = :market AND p.geom_local IS NOT NULL "
)
_ORDER = " ORDER BY md5(p.parcel_number) LIMIT :limit"


@dataclass(frozen=True)
class CategorySelector:
    category: GoldCategory
    predicate: str
    rationale: str


SELECTORS: tuple[CategorySelector, ...] = (
    CategorySelector(
        "standard_rsa_rowhouse",
        "AND replace(upper(p.base_zoning_code), '-', '') LIKE 'RSA%' "
        "AND p.lot_area_sqft BETWEEN 800 AND 2500",
        "Typical rowhouse envelope in an RSA district.",
    ),
    CategorySelector(
        "undersized_lot",
        "AND replace(upper(p.base_zoning_code), '-', '') = 'RSA5' "
        "AND p.lot_area_sqft > 0 AND p.lot_area_sqft < 1440",
        "Below the RSA-5 minimum lot area.",
    ),
    CategorySelector(
        "oversized_or_double_lot",
        "AND p.lot_area_sqft > 3000",
        "Large enough to read as a double lot or subdivision candidate.",
    ),
    CategorySelector(
        "corner_or_irregular",
        "AND ST_NPoints(p.geom_local) > 8",
        "Polygon has more vertices than a rectangle; a corner or irregular-shape candidate.",
    ),
    CategorySelector(
        "assemblage_candidate",
        "AND EXISTS (SELECT 1 FROM parcel_assemblage a WHERE a.parcel_number = p.parcel_number)",
        "Already identified as part of an assemblage play.",
    ),
    CategorySelector(
        "mixed_use_district",
        "AND replace(upper(p.base_zoning_code), '-', '') LIKE 'CMX%'",
        "Commercial mixed-use base district.",
    ),
    CategorySelector(
        "multifamily_district",
        "AND replace(upper(p.base_zoning_code), '-', '') LIKE 'RM%'",
        "Multi-family base district.",
    ),
    CategorySelector(
        "industrial",
        "AND replace(upper(p.base_zoning_code), '-', '') LIKE 'I%'",
        "Industrial base district.",
    ),
    CategorySelector(
        "special_purpose_district",
        "AND replace(upper(p.base_zoning_code), '-', '') LIKE 'SP%'",
        "Special-purpose base district.",
    ),
    CategorySelector(
        "historic",
        "AND EXISTS (SELECT 1 FROM historic_district h "
        "WHERE ST_Intersects(h.geom_local, p.geom_local))",
        "Intersects a mapped historic district, read from the source layer.",
    ),
    CategorySelector(
        "flood_exposure",
        "AND EXISTS (SELECT 1 FROM flood_zone f WHERE ST_Intersects(f.geom_local, p.geom_local))",
        "Intersects a FEMA flood polygon, read from the source layer.",
    ),
    CategorySelector(
        "public_ownership",
        "AND (p.owner ILIKE '%PHILADELPHIA LAND BANK%' OR p.owner ILIKE '%REDEVELOPMENT AUTH%' "
        "OR p.owner ILIKE '%CITY OF PHILA%' OR p.owner ILIKE '%PHDC%')",
        "Owner of record is a public land-holding body.",
    ),
    CategorySelector(
        "tax_delinquency",
        "AND EXISTS (SELECT 1 FROM tax_status t WHERE t.parcel_number = p.parcel_number "
        "AND t.total_due > 0)",
        "Outstanding balance in the Revenue dataset.",
    ),
    CategorySelector(
        "access_problem",
        "AND NOT EXISTS (SELECT 1 FROM street_centerline s "
        "WHERE ST_DWithin(s.geom_local, p.geom_local, 50))",
        "No street centerline within 50 ft; a landlocked candidate.",
    ),
    CategorySelector(
        "developed_appearing_vacant",
        "AND p.is_vacant IS TRUE AND p.land_use IS NOT NULL "
        "AND upper(p.land_use) NOT LIKE 'VACANT%'",
        "Flagged vacant while the recorded land use describes a structure.",
    ),
    CategorySelector(
        "known_permit",
        "AND EXISTS (SELECT 1 FROM li_event e WHERE e.parcel_number = p.parcel_number "
        "AND e.event_type = 'permit')",
        "Has a recorded L&I permit.",
    ),
    CategorySelector(
        "zoning_appeal",
        "AND EXISTS (SELECT 1 FROM zba_appeal z WHERE z.parcel_number = p.parcel_number)",
        "Has a recorded ZBA appeal.",
    ),
)


async def select_parcels_for_category(
    session: AsyncSession, selector: CategorySelector, *, market: str, limit: int
) -> list[str]:
    statement = text(_BASE + selector.predicate + _ORDER)
    result = await session.execute(statement, {"market": market, "limit": limit})
    return [row[0] for row in result]


def merge_into_cases(assignments: dict[str, list[GoldCategory]]) -> list[GoldCase]:
    return [
        GoldCase(
            parcel_number=parcel_number,
            categories=sorted(set(categories)),
            expected=ExpectedFacts(),
            review_status="unreviewed",
        )
        for parcel_number, categories in sorted(assignments.items())
    ]


async def select_gold_set(
    session: AsyncSession, *, market: str, per_category: int
) -> tuple[list[GoldCase], dict[str, int]]:
    assignments: dict[str, list[GoldCategory]] = {}
    found: dict[str, int] = {}
    for selector in SELECTORS:
        parcels = await select_parcels_for_category(
            session, selector, market=market, limit=per_category
        )
        found[selector.category] = len(parcels)
        for parcel_number in parcels:
            assignments.setdefault(parcel_number, []).append(selector.category)
    return merge_into_cases(assignments), found
