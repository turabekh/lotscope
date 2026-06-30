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

_PARCEL_SQL = text("SELECT market_value FROM parcel WHERE parcel_number = :parcel_number")

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

    valuation = await value_parcel(
        session, parcel_number, radius_ft=radius_ft, years=years, since=since
    )
    analysis = analyze_assessment(
        AssessmentInputs(
            assessed_market_value=_as_float(parcel.market_value),
            market_estimate=valuation.estimate if valuation is not None else None,
            market_low=valuation.low if valuation is not None else None,
            market_high=valuation.high if valuation is not None else None,
            valuation_confidence=valuation.confidence if valuation is not None else None,
        )
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
        reasons=analysis.reasons,
        disclaimer=ASSESSMENT_DISCLAIMER,
        sources=_SOURCES,
        computed_at=datetime.now(UTC),
    )
