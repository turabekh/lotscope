from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.valuation.avm import Comp, estimate_land_value, land_use_class, price_per_sqft
from lotscope.valuation.schemas import CompResult, ValuationResult

DEFAULT_RADIUS_FT = 1500.0
DEFAULT_YEARS = 3
DEFAULT_MIN_PRICE = 1000.0
DEFAULT_LIMIT = 25

_SUBJECT_SQL = text(
    "SELECT lot_area_sqft, base_zoning_code, (geom_2272 IS NOT NULL) AS has_geometry "
    "FROM parcel WHERE parcel_number = :parcel_number"
)
_COMPS_SQL = text(
    "WITH subject AS ("
    "  SELECT ST_Centroid(geom_2272) AS pt FROM parcel WHERE parcel_number = :parcel_number"
    ") "
    "SELECT s.parcel_number AS parcel_number, "
    "       ST_Distance(subject.pt, ST_Centroid(cp.geom_2272)) AS distance_ft, "
    "       s.sale_price AS sale_price, "
    "       s.sale_date AS sale_date, "
    "       cp.lot_area_sqft AS lot_area_sqft "
    "FROM sale s "
    "JOIN parcel cp ON cp.parcel_number = s.parcel_number "
    "CROSS JOIN subject "
    "WHERE cp.geom_2272 IS NOT NULL "
    "  AND s.parcel_number <> :parcel_number "
    "  AND s.sale_price >= :min_price "
    "  AND s.sale_date >= :since "
    "  AND (NOT :vacant_only OR cp.is_vacant IS TRUE) "
    "  AND ((:use_class)::text IS NULL OR CASE left(upper(cp.base_zoning_code), 1) "
    "         WHEN 'R' THEN 'residential' WHEN 'C' THEN 'commercial' "
    "         WHEN 'I' THEN 'industrial' WHEN 'S' THEN 'special' ELSE NULL END "
    "       = (:use_class)::text) "
    "  AND ST_DWithin(cp.geom_2272, subject.pt, :radius_ft) "
    "ORDER BY distance_ft "
    "LIMIT :limit"
)


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


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
) -> list[Comp]:
    cutoff = since if since is not None else date.today() - timedelta(days=365 * years)
    rows = await session.execute(
        _COMPS_SQL,
        {
            "parcel_number": parcel_number,
            "min_price": min_price,
            "since": cutoff,
            "vacant_only": vacant_only,
            "radius_ft": radius_ft,
            "limit": limit,
            "use_class": use_class,
        },
    )
    comps: list[Comp] = []
    for row in rows:
        sale_price = float(row.sale_price)
        lot_area = _as_float(row.lot_area_sqft)
        comps.append(
            Comp(
                parcel_number=row.parcel_number,
                distance_ft=float(row.distance_ft),
                sale_price=sale_price,
                sale_date=row.sale_date,
                lot_area_sqft=lot_area,
                price_per_sqft=price_per_sqft(sale_price, lot_area),
            )
        )
    return comps


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
    comps: list[Comp] = []
    if subject.has_geometry:
        comps = await find_comps(
            session,
            parcel_number,
            radius_ft=radius_ft,
            years=years,
            vacant_only=vacant_only,
            since=since,
            use_class=use_class,
        )

    estimate = estimate_land_value(_as_float(subject.lot_area_sqft), comps)
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
                distance_ft=comp.distance_ft,
                sale_price=comp.sale_price,
                sale_date=comp.sale_date,
                lot_area_sqft=comp.lot_area_sqft,
                price_per_sqft=comp.price_per_sqft,
            )
            for comp in comps
        ],
        reasons=estimate.reasons,
        sources=[
            {
                "source": "rtt_summary",
                "comp_count": len(comps),
                "radius_ft": radius_ft,
                "years": years,
                "use_class": use_class,
            }
        ],
        computed_at=computed_at,
    )
