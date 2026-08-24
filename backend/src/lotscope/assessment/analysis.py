from dataclasses import dataclass
from typing import Literal

AssessmentStatus = Literal["over_assessed", "fairly_assessed", "under_assessed", "unknown"]
Confidence = Literal["high", "medium", "low"]

PHILADELPHIA_REALTY_TAX_RATE = 0.013998
ASSESSMENT_GAP_THRESHOLD = 0.10

ASSESSMENT_DISCLAIMER = (
    "Informational estimate only, not tax or legal advice. Savings are gross of homestead, "
    "LOOP, and abatement exemptions and assume the assessment is reduced to the modeled market "
    "value. Confirm with a tax professional and the Office of Property Assessment before filing."
)


@dataclass(frozen=True)
class AssessmentInputs:
    assessed_market_value: float | None
    market_estimate: float | None
    market_low: float | None
    market_high: float | None
    valuation_confidence: Confidence | None
    is_vacant: bool | None = None


@dataclass(frozen=True)
class AssessmentAnalysis:
    status: AssessmentStatus
    assessed_market_value: float | None
    market_estimate: float | None
    market_low: float | None
    market_high: float | None
    gap: float | None
    gap_pct: float | None
    over_assessed_amount: float | None
    estimated_annual_tax_savings: float | None
    tax_rate: float
    confidence: Confidence
    reasons: list[str]


def _classify(assessed: float, estimate: float) -> AssessmentStatus:
    ratio = (estimate - assessed) / assessed
    if ratio <= -ASSESSMENT_GAP_THRESHOLD:
        return "over_assessed"
    if ratio >= ASSESSMENT_GAP_THRESHOLD:
        return "under_assessed"
    return "fairly_assessed"


NOT_VACANT_REASON = (
    "This parcel is not a vacant lot, and the market estimate it would be compared against is "
    "built from vacant-land sales. Comparing a developed property to land comps understates its "
    "value, so no over-assessment or savings figure is shown."
)


def _not_evaluated(inputs: AssessmentInputs, reason: str) -> AssessmentAnalysis:
    return AssessmentAnalysis(
        status="unknown",
        assessed_market_value=inputs.assessed_market_value,
        market_estimate=inputs.market_estimate,
        market_low=inputs.market_low,
        market_high=inputs.market_high,
        gap=None,
        gap_pct=None,
        over_assessed_amount=None,
        estimated_annual_tax_savings=None,
        tax_rate=PHILADELPHIA_REALTY_TAX_RATE,
        confidence="low",
        reasons=[reason],
    )


def analyze_assessment(inputs: AssessmentInputs) -> AssessmentAnalysis:
    assessed = inputs.assessed_market_value
    estimate = inputs.market_estimate
    if assessed is None or assessed <= 0 or estimate is None:
        return _not_evaluated(
            inputs, "Not enough assessment or comp data to evaluate the assessment."
        )
    if inputs.is_vacant is not True:
        return _not_evaluated(inputs, NOT_VACANT_REASON)

    gap = estimate - assessed
    gap_pct = gap / assessed
    status = _classify(assessed, estimate)
    confidence: Confidence = inputs.valuation_confidence or "low"

    reasons: list[str] = []
    over_assessed_amount: float | None = None
    estimated_annual_tax_savings: float | None = None
    if status == "over_assessed":
        over_assessed_amount = assessed - estimate
        estimated_annual_tax_savings = round(over_assessed_amount * PHILADELPHIA_REALTY_TAX_RATE, 0)
        reasons.append(
            f"Assessed at ${assessed:,.0f} versus a modeled market value of ${estimate:,.0f} "
            f"({gap_pct:.0%}); a successful appeal could save roughly "
            f"${estimated_annual_tax_savings:,.0f} per year."
        )
    elif status == "under_assessed":
        reasons.append(
            f"Assessed at ${assessed:,.0f}, below the modeled market value of ${estimate:,.0f} "
            f"(+{gap_pct:.0%}); little tax-appeal upside."
        )
    else:
        reasons.append(
            f"Assessed at ${assessed:,.0f} versus a modeled market value of ${estimate:,.0f}; "
            "within the normal range."
        )
    if confidence == "low":
        reasons.append("Comparable sales are thin, so treat this as a low-confidence signal.")

    return AssessmentAnalysis(
        status=status,
        assessed_market_value=assessed,
        market_estimate=estimate,
        market_low=inputs.market_low,
        market_high=inputs.market_high,
        gap=round(gap, 0),
        gap_pct=round(gap_pct, 4),
        over_assessed_amount=over_assessed_amount,
        estimated_annual_tax_savings=estimated_annual_tax_savings,
        tax_rate=PHILADELPHIA_REALTY_TAX_RATE,
        confidence=confidence,
        reasons=reasons,
    )
