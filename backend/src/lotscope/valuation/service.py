from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.sql import future_sale_exclusion_sql, package_deed_exclusion_sql
from lotscope.valuation.avm import (
    Comp,
    estimate_land_value,
    is_related_party,
    land_use_class,
    price_per_sqft,
    select_size_similar_comps,
    wide_area_use_classes,
)
from lotscope.valuation.fallback import WIDE_AREA
from lotscope.valuation.policy import (
    COMP_SELECTION,
    excluded_document_types,
)
from lotscope.valuation.schemas import (
    CompResult,
    SheriffClearingEstimate,
    ValuationResult,
)

DEFAULT_RADIUS_FT = 1500.0
DEFAULT_YEARS = 3
DEFAULT_MIN_PRICE = 1000.0
DEFAULT_LIMIT = 25

SHERIFF_DEED_DOCUMENT_TYPE = "SHERIFF'S DEED"
CLEARING_RADIUS_M = 800.0
CLEARING_RADIUS_FT = CLEARING_RADIUS_M / 0.3048
CLEARING_MONTHS = 24
CLEARING_MINIMUM_SAMPLE = 3
CLEARING_SOURCE = "rtt_summary"
CLEARING_SOURCE_URL = "https://opendataphilly.org/datasets/real-estate-transfers/"

_CLEARING_SQL = text(
    "WITH subject AS ("
    "  SELECT geom_local, "
    "  regexp_replace(upper(coalesce(nullif(base_zoning_code, ''), resolved_zoning_code)), "
    "  '[^A-Z].*$', '') AS zoning_class "
    "  FROM parcel WHERE parcel_number = :parcel_number"
    ") "
    "SELECT count(*) AS sample_size, "
    "percentile_cont(0.5) WITHIN GROUP (ORDER BY s.sale_price) AS median_price, "
    "min(s.sale_price) AS low, max(s.sale_price) AS high, "
    "max(subject.zoning_class) AS zoning_class "
    "FROM subject "
    "JOIN parcel c ON c.geom_local IS NOT NULL "
    "AND ST_DWithin(c.geom_local, subject.geom_local, :radius_ft) "
    "AND c.is_vacant IS TRUE "
    "AND regexp_replace(upper(coalesce(nullif(c.base_zoning_code, ''), c.resolved_zoning_code)), "
    "'[^A-Z].*$', '') = subject.zoning_class "
    "JOIN sale s ON s.parcel_number = c.parcel_number "
    "AND s.document_type = :document_type "
    "AND s.sale_date >= current_date - make_interval(months => :months) "
    "AND s.sale_price > 0"
)

_SUBJECT_SQL = text(
    "SELECT lot_area_sqft, base_zoning_code, market_code, (geom_local IS NOT NULL) AS has_geometry "
    "FROM parcel WHERE parcel_number = :parcel_number"
)
_COMPS_SQL = text(
    "WITH subject AS ("
    "  SELECT ST_Centroid(geom_local) AS pt, market_code "
    "  FROM parcel WHERE parcel_number = :parcel_number"
    ") "
    "SELECT s.parcel_number AS parcel_number, "
    "       cp.address AS address, "
    "       ST_Distance(subject.pt, ST_Centroid(cp.geom_local)) AS distance_ft, "
    "       s.sale_price AS sale_price, "
    "       s.sale_date AS sale_date, "
    "       s.grantor AS grantor, "
    "       s.grantee AS grantee, "
    "       cp.lot_area_sqft AS lot_area_sqft "
    "FROM sale s "
    "JOIN parcel cp ON cp.parcel_number = s.parcel_number "
    "CROSS JOIN subject "
    "WHERE cp.geom_local IS NOT NULL "
    "  AND cp.market_code = subject.market_code "
    "  AND s.parcel_number <> :parcel_number "
    "  AND s.sale_price >= :min_price "
    "  AND s.sale_date >= :since "
    "  AND " + future_sale_exclusion_sql("s") + " "
    "  AND " + package_deed_exclusion_sql("s") + " "
    "  AND (NOT :vacant_only OR cp.is_vacant IS TRUE) "
    "  AND ((:excluded_document_types)::text[] IS NULL OR s.document_type IS NULL "
    "       OR NOT (upper(btrim(s.document_type)) = ANY((:excluded_document_types)::text[]))) "
    "  AND ((:use_classes)::text[] IS NULL OR CASE left(upper(cp.base_zoning_code), 1) "
    "         WHEN 'R' THEN 'residential' WHEN 'C' THEN 'commercial' "
    "         WHEN 'I' THEN 'industrial' WHEN 'S' THEN 'special' ELSE NULL END "
    "       = ANY((:use_classes)::text[])) "
    "  AND ST_DWithin(cp.geom_local, subject.pt, :radius_ft) "
    "ORDER BY distance_ft "
    "LIMIT :limit"
)


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


async def sheriff_clearing_estimate(
    session: AsyncSession, parcel_number: str
) -> SheriffClearingEstimate:
    computed_at = datetime.now(UTC)
    row = (
        await session.execute(
            _CLEARING_SQL,
            {
                "parcel_number": parcel_number,
                "radius_ft": CLEARING_RADIUS_FT,
                "document_type": SHERIFF_DEED_DOCUMENT_TYPE,
                "months": CLEARING_MONTHS,
            },
        )
    ).one_or_none()

    sample = int(row.sample_size) if row is not None else 0
    zoning_class = row.zoning_class if row is not None else None
    base = {
        "parcel_number": parcel_number,
        "zoning_class": zoning_class,
        "sample_size": sample,
        "radius_m": CLEARING_RADIUS_M,
        "months": CLEARING_MONTHS,
        "minimum_sample": CLEARING_MINIMUM_SAMPLE,
        "source": CLEARING_SOURCE,
        "source_url": CLEARING_SOURCE_URL,
        "computed_at": computed_at,
    }

    if zoning_class is None:
        return SheriffClearingEstimate(
            sufficient=False,
            reason="The parcel has no zoning district recorded, so no comparable class exists.",
            **base,
        )
    if sample < CLEARING_MINIMUM_SAMPLE:
        return SheriffClearingEstimate(
            sufficient=False,
            reason=(
                f"Only {sample} sheriff's deed"
                f"{'' if sample == 1 else 's'} on {zoning_class} vacant land within "
                f"{CLEARING_RADIUS_M:.0f} m in {CLEARING_MONTHS} months; "
                f"{CLEARING_MINIMUM_SAMPLE} are needed."
            ),
            **base,
        )

    assert row is not None
    return SheriffClearingEstimate(
        sufficient=True,
        estimate=_as_float(row.median_price),
        low=_as_float(row.low),
        high=_as_float(row.high),
        **base,
    )


async def find_comps(
    session: AsyncSession,
    parcel_number: str,
    *,
    radius_ft: float = DEFAULT_RADIUS_FT,
    years: int = DEFAULT_YEARS,
    min_price: float = DEFAULT_MIN_PRICE,
    limit: int = DEFAULT_LIMIT,
    vacant_only: bool = True,
    since: date | None = None,
    use_class: str | None = None,
    use_classes: list[str] | None = None,
    excluded_document_types: list[str] | None = None,
) -> tuple[list[Comp], int]:
    cutoff = since if since is not None else date.today() - timedelta(days=365 * years)
    accepted = use_classes if use_classes is not None else ([use_class] if use_class else None)
    rows = await session.execute(
        _COMPS_SQL,
        {
            "parcel_number": parcel_number,
            "min_price": min_price,
            "since": cutoff,
            "vacant_only": vacant_only,
            "radius_ft": radius_ft,
            "limit": limit,
            "use_classes": accepted,
            "excluded_document_types": excluded_document_types,
        },
    )
    comps: list[Comp] = []
    related_party_excluded = 0
    for row in rows:
        if is_related_party(row.grantor, row.grantee):
            related_party_excluded += 1
            continue
        sale_price = float(row.sale_price)
        lot_area = _as_float(row.lot_area_sqft)
        comps.append(
            Comp(
                parcel_number=row.parcel_number,
                address=row.address,
                distance_ft=float(row.distance_ft),
                sale_price=sale_price,
                sale_date=row.sale_date,
                lot_area_sqft=lot_area,
                price_per_sqft=price_per_sqft(sale_price, lot_area),
            )
        )
    return comps, related_party_excluded


async def value_parcel(
    session: AsyncSession,
    parcel_number: str,
    *,
    radius_ft: float = DEFAULT_RADIUS_FT,
    years: int = DEFAULT_YEARS,
    vacant_only: bool = True,
    since: date | None = None,
    segment_by_use_class: bool = True,
) -> ValuationResult | None:
    subject = (await session.execute(_SUBJECT_SQL, {"parcel_number": parcel_number})).one_or_none()
    if subject is None:
        return None
    computed_at = datetime.now(UTC)

    use_class = land_use_class(subject.base_zoning_code) if segment_by_use_class else None
    excluded = excluded_document_types()
    subject_area = _as_float(subject.lot_area_sqft)
    comps: list[Comp] = []
    related_party_excluded = 0
    wide_area = False
    if subject.has_geometry:
        comps, related_party_excluded = await find_comps(
            session,
            parcel_number,
            radius_ft=radius_ft,
            years=years,
            vacant_only=vacant_only,
            since=since,
            use_class=use_class,
            excluded_document_types=excluded,
        )
        if not comps and since is None:
            wide_area = True
            comps, related_party_excluded = await find_comps(
                session,
                parcel_number,
                radius_ft=WIDE_AREA.radius_ft,
                years=WIDE_AREA.years,
                vacant_only=vacant_only,
                use_classes=wide_area_use_classes(use_class),
                excluded_document_types=excluded,
            )

    comps, size_narrowed = select_size_similar_comps(
        comps,
        subject_area,
        ratio_min=COMP_SELECTION.lot_area_ratio_min,
        ratio_max=COMP_SELECTION.lot_area_ratio_max,
        min_similar_comps=COMP_SELECTION.min_similar_comps,
    )

    estimate = estimate_land_value(
        subject_area,
        comps,
        related_party_excluded=related_party_excluded,
        wide_area=wide_area,
        size_narrowed_to=(
            (COMP_SELECTION.lot_area_ratio_min, COMP_SELECTION.lot_area_ratio_max)
            if size_narrowed
            else None
        ),
    )
    return ValuationResult(
        parcel_number=parcel_number,
        estimate=estimate.estimate,
        low=estimate.low,
        high=estimate.high,
        price_per_sqft=estimate.price_per_sqft,
        confidence=estimate.confidence,
        comp_count=estimate.comp_count,
        coefficient_of_variation=estimate.coefficient_of_variation,
        comps=[
            CompResult(
                parcel_number=comp.parcel_number,
                address=comp.address,
                distance_ft=comp.distance_ft,
                sale_price=comp.sale_price,
                sale_date=comp.sale_date,
                lot_area_sqft=comp.lot_area_sqft,
                price_per_sqft=comp.price_per_sqft,
            )
            for comp in comps
        ],
        reasons=estimate.reasons,
        wide_area=wide_area,
        sources=[
            {
                "source": "rtt_summary",
                "comp_count": len(comps),
                "radius_ft": WIDE_AREA.radius_ft if wide_area else radius_ft,
                "years": WIDE_AREA.years if wide_area else years,
                "use_class": use_class,
                "use_classes": wide_area_use_classes(use_class) if wide_area else None,
                "comp_tier": "wide_area" if wide_area else "local",
                "package_deeds_excluded": True,
                "comp_selection_policy": COMP_SELECTION.version,
                "excluded_document_types": excluded,
                "size_similar_only": size_narrowed,
            }
        ],
        computed_at=computed_at,
    )
