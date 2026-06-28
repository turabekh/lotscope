from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.distress.schemas import DistressFactor, DistressResult, LeadItem
from lotscope.distress.scoring import (
    _ABSENTEE_WEIGHT,
    _DANGEROUS_WEIGHT,
    _DELINQUENT_WEIGHT,
    _DEMOLITION_WEIGHT,
    _LIEN_WEIGHT,
    _SEVERE_DELINQUENT_WEIGHT,
    _SEVERE_DUE,
    _SEVERE_YEARS,
    _SHERIFF_SALE_WEIGHT,
    _VACANT_WEIGHT,
    _VIOLATION_WEIGHT,
    DistressSignals,
    is_absentee,
    score_distress,
)

_SOURCES: list[dict[str, Any]] = [
    {"source": "tax_status"},
    {"source": "li_event"},
    {"source": "parcel"},
]

_PARCEL_DISTRESS_SQL = text(
    "SELECT p.is_vacant, p.is_city_owned, p.address, p.mailing_address, "
    "ts.is_delinquent, ts.total_due, ts.years_owed, ts.lien_count, ts.in_sheriff_sale, "
    "coalesce(li.dangerous, false) AS dangerous, "
    "coalesce(li.violations, 0) AS violations, "
    "coalesce(li.demolitions, 0) AS demolitions "
    "FROM parcel p "
    "LEFT JOIN tax_status ts ON ts.parcel_number = p.parcel_number "
    "LEFT JOIN ("
    "  SELECT parcel_number, "
    "  bool_or(coalesce(is_unsafe, false) OR coalesce(is_imminently_dangerous, false)) "
    "  AS dangerous, "
    "  count(*) FILTER (WHERE event_type = 'violation') AS violations, "
    "  count(*) FILTER (WHERE event_type = 'demolition') AS demolitions "
    "  FROM li_event WHERE parcel_number = :parcel_number GROUP BY parcel_number"
    ") li ON li.parcel_number = p.parcel_number "
    "WHERE p.parcel_number = :parcel_number"
)

_LEADS_SQL = text(
    f"""
WITH li AS (
  SELECT parcel_number,
    bool_or(coalesce(is_unsafe, false) OR coalesce(is_imminently_dangerous, false)) AS dangerous,
    count(*) FILTER (WHERE event_type = 'violation') AS violations,
    count(*) FILTER (WHERE event_type = 'demolition') AS demolitions
  FROM li_event GROUP BY parcel_number
),
scored AS (
  SELECT p.parcel_number, p.address, p.owner, p.base_zoning_code, p.is_vacant, p.market_value,
    ts.total_due, ts.in_sheriff_sale,
    LEAST(100,
      (CASE WHEN ts.in_sheriff_sale THEN {_SHERIFF_SALE_WEIGHT} ELSE 0 END)
      + (CASE WHEN ts.is_delinquent THEN {_DELINQUENT_WEIGHT} ELSE 0 END)
      + (CASE WHEN ts.is_delinquent AND (coalesce(ts.total_due, 0) >= {_SEVERE_DUE}
             OR coalesce(ts.years_owed, 0) >= {_SEVERE_YEARS}) THEN {_SEVERE_DELINQUENT_WEIGHT}
             ELSE 0 END)
      + (CASE WHEN coalesce(ts.lien_count, 0) > 0 THEN {_LIEN_WEIGHT} ELSE 0 END)
      + (CASE WHEN li.dangerous THEN {_DANGEROUS_WEIGHT}
             WHEN coalesce(li.violations, 0) > 0 THEN {_VIOLATION_WEIGHT} ELSE 0 END)
      + (CASE WHEN coalesce(li.demolitions, 0) > 0 THEN {_DEMOLITION_WEIGHT} ELSE 0 END)
      + (CASE WHEN coalesce(p.is_vacant, false) THEN {_VACANT_WEIGHT} ELSE 0 END)
      + (CASE WHEN p.mailing_address IS NOT NULL AND p.address IS NOT NULL
             AND position(upper(p.address) in upper(p.mailing_address)) = 0
             THEN {_ABSENTEE_WEIGHT} ELSE 0 END)
    ) AS score
  FROM parcel p
  LEFT JOIN tax_status ts ON ts.parcel_number = p.parcel_number
  LEFT JOIN li ON li.parcel_number = p.parcel_number
  WHERE coalesce(p.is_city_owned, false) = false
    AND (coalesce(ts.is_delinquent, false) OR coalesce(ts.in_sheriff_sale, false)
         OR coalesce(p.is_vacant, false) OR coalesce(li.dangerous, false)
         OR coalesce(li.violations, 0) > 0)
    AND (NOT CAST(:vacant_only AS boolean) OR coalesce(p.is_vacant, false))
    AND (CAST(:zip_code AS text) IS NULL OR p.zip_code = CAST(:zip_code AS text))
)
SELECT * FROM scored WHERE score >= CAST(:min_score AS integer)
ORDER BY score DESC, coalesce(total_due, 0) DESC, parcel_number
LIMIT CAST(:limit AS integer)
"""
)


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def _signals(row: Row[Any]) -> DistressSignals:
    return DistressSignals(
        in_sheriff_sale=bool(row.in_sheriff_sale),
        is_delinquent=bool(row.is_delinquent),
        total_due=_as_float(row.total_due),
        years_owed=row.years_owed,
        lien_count=row.lien_count,
        has_imminently_dangerous=bool(row.dangerous),
        violations=row.violations,
        demolitions=row.demolitions,
        is_vacant=bool(row.is_vacant),
        is_absentee_owner=is_absentee(row.address, row.mailing_address),
        is_city_owned=bool(row.is_city_owned),
    )


async def assess_parcel_distress(
    session: AsyncSession, parcel_number: str
) -> DistressResult | None:
    row = (
        await session.execute(_PARCEL_DISTRESS_SQL, {"parcel_number": parcel_number})
    ).one_or_none()
    if row is None:
        return None
    assessment = score_distress(_signals(row))
    return DistressResult(
        parcel_number=parcel_number,
        score=assessment.score,
        tier=assessment.tier,
        factors=[
            DistressFactor(code=f.code, label=f.label, weight=f.weight) for f in assessment.factors
        ],
        sources=_SOURCES,
        computed_at=datetime.now(UTC),
    )


def _lead_top_factors(row: Row[Any]) -> list[str]:
    factors: list[str] = []
    if row.in_sheriff_sale:
        factors.append("Sheriff sale")
    if row.total_due:
        factors.append(f"${float(row.total_due):,.0f} owed")
    if row.is_vacant:
        factors.append("Vacant")
    return factors


async def find_leads(
    session: AsyncSession,
    *,
    limit: int,
    min_score: int = 1,
    vacant_only: bool = False,
    zip_code: str | None = None,
) -> list[LeadItem]:
    rows = (
        await session.execute(
            _LEADS_SQL,
            {
                "limit": limit,
                "min_score": min_score,
                "vacant_only": vacant_only,
                "zip_code": zip_code,
            },
        )
    ).all()
    return [
        LeadItem(
            parcel_number=row.parcel_number,
            address=row.address,
            owner=row.owner,
            base_zoning_code=row.base_zoning_code,
            is_vacant=row.is_vacant,
            market_value=_as_float(row.market_value),
            total_due=_as_float(row.total_due),
            in_sheriff_sale=row.in_sheriff_sale,
            score=int(row.score),
            top_factors=_lead_top_factors(row),
        )
        for row in rows
    ]
