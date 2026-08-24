from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.assessment.analysis import (
    ASSESSMENT_DISCLAIMER,
    AssessmentInputs,
    analyze_assessment,
)
from lotscope.assessment.schemas import AssessmentResult
from lotscope.valuation.service import value_parcel

_PARCEL_SQL = text(
    "SELECT p.market_value, p.is_vacant, m.assessment_ratio FROM parcel p "
    "JOIN market m ON m.code = p.market_code WHERE p.parcel_number = :parcel_number"
)

_SOURCES: list[dict[str, Any]] = [{"source": "opa_properties_public"}, {"source": "rtt_summary"}]


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


async def analyze_parcel_assessment(
    session: AsyncSession,
    parcel_number: str,
    *,
    radius_ft: float = 1500.0,
    years: int = 3,
    since: date | None = None,
) -> AssessmentResult | None:
    parcel = (await session.execute(_PARCEL_SQL, {"parcel_number": parcel_number})).one_or_none()
    if parcel is None:
        return None

    ratio = _as_float(parcel.assessment_ratio)
    if ratio is None or ratio <= 0:
        return None

    assessed = _as_float(parcel.market_value)
    implied_market_value = assessed / ratio if assessed is not None else None

    valuation = await value_parcel(
        session, parcel_number, radius_ft=radius_ft, years=years, since=since
    )
    analysis = analyze_assessment(
        AssessmentInputs(
            assessed_market_value=implied_market_value,
            market_estimate=valuation.estimate if valuation is not None else None,
            market_low=valuation.low if valuation is not None else None,
            market_high=valuation.high if valuation is not None else None,
            valuation_confidence=valuation.confidence if valuation is not None else None,
            is_vacant=parcel.is_vacant,
        )
    )
    reasons = list(analysis.reasons)
    if ratio != 1.0:
        reasons.insert(
            0,
            "Market value shown is implied from the assessed value via the county "
            f"common level ratio ({ratio:.4f}); the raw assessment is a base-year figure.",
        )

    return AssessmentResult(
        parcel_number=parcel_number,
        status=analysis.status,
        assessed_market_value=analysis.assessed_market_value,
        market_estimate=analysis.market_estimate,
        market_low=analysis.market_low,
        market_high=analysis.market_high,
        gap=analysis.gap,
        gap_pct=analysis.gap_pct,
        over_assessed_amount=analysis.over_assessed_amount,
        estimated_annual_tax_savings=analysis.estimated_annual_tax_savings,
        tax_rate=analysis.tax_rate,
        confidence=analysis.confidence,
        reasons=reasons,
        disclaimer=ASSESSMENT_DISCLAIMER,
        sources=_SOURCES,
        computed_at=datetime.now(UTC),
    )
