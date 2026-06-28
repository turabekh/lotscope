from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.distress.models import ParcelDistress
from lotscope.distress.schemas import DistressFactor, DistressResult, LeadItem
from lotscope.distress.scoring import DistressSignals, is_absentee, score_distress

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

_BULK_SIGNALS_SQL = text(
    "SELECT p.parcel_number, p.is_vacant, p.is_city_owned, p.address, p.mailing_address, "
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
    "  FROM li_event WHERE parcel_number = ANY(:parcel_numbers) GROUP BY parcel_number"
    ") li ON li.parcel_number = p.parcel_number "
    "WHERE p.parcel_number = ANY(:parcel_numbers)"
)

_LEADS_SQL = text(
    "SELECT p.parcel_number, p.address, p.owner, p.base_zoning_code, p.is_vacant, p.market_value, "
    "ts.total_due, ts.in_sheriff_sale, pd.score "
    "FROM parcel_distress pd "
    "JOIN parcel p ON p.parcel_number = pd.parcel_number "
    "LEFT JOIN tax_status ts ON ts.parcel_number = p.parcel_number "
    "WHERE pd.score >= CAST(:min_score AS integer) "
    "AND coalesce(p.is_city_owned, false) = false "
    "AND (NOT CAST(:vacant_only AS boolean) OR coalesce(p.is_vacant, false)) "
    "AND (CAST(:zip_code AS text) IS NULL OR p.zip_code = CAST(:zip_code AS text)) "
    "ORDER BY pd.score DESC, coalesce(ts.total_due, 0) DESC, p.parcel_number "
    "LIMIT CAST(:limit AS integer)"
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


async def recompute_distress(session: AsyncSession, parcel_numbers: Sequence[str]) -> int:
    if not parcel_numbers:
        return 0
    rows = (
        await session.execute(_BULK_SIGNALS_SQL, {"parcel_numbers": list(parcel_numbers)})
    ).all()
    if not rows:
        return 0
    now = datetime.now(UTC)
    values = []
    for row in rows:
        assessment = score_distress(_signals(row))
        values.append(
            {
                "parcel_number": row.parcel_number,
                "score": assessment.score,
                "tier": assessment.tier,
                "sources": _SOURCES,
                "computed_at": now,
            }
        )
    statement = insert(ParcelDistress).values(values)
    statement = statement.on_conflict_do_update(
        index_elements=["parcel_number"],
        set_={
            "score": statement.excluded.score,
            "tier": statement.excluded.tier,
            "sources": statement.excluded.sources,
            "computed_at": statement.excluded.computed_at,
        },
    )
    await session.execute(statement)
    return len(values)


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
