from lotscope.assessment.analysis import (
    PHILADELPHIA_REALTY_TAX_RATE,
    AssessmentInputs,
    analyze_assessment,
)


def _inputs(**overrides: object) -> AssessmentInputs:
    base: dict[str, object] = {
        "assessed_market_value": 200000.0,
        "market_estimate": 200000.0,
        "market_low": 180000.0,
        "market_high": 220000.0,
        "valuation_confidence": "high",
    }
    base.update(overrides)
    return AssessmentInputs(**base)  # type: ignore[arg-type]


def test_over_assessed_when_assessment_exceeds_market() -> None:
    result = analyze_assessment(_inputs(assessed_market_value=300000.0, market_estimate=200000.0))
    assert result.status == "over_assessed"
    assert result.over_assessed_amount == 100000.0
    assert result.estimated_annual_tax_savings == round(100000.0 * PHILADELPHIA_REALTY_TAX_RATE, 0)


def test_under_assessed_when_market_exceeds_assessment() -> None:
    result = analyze_assessment(_inputs(assessed_market_value=200000.0, market_estimate=300000.0))
    assert result.status == "under_assessed"
    assert result.over_assessed_amount is None
    assert result.estimated_annual_tax_savings is None


def test_fairly_assessed_within_threshold() -> None:
    result = analyze_assessment(_inputs(assessed_market_value=200000.0, market_estimate=205000.0))
    assert result.status == "fairly_assessed"
    assert result.estimated_annual_tax_savings is None


def test_unknown_without_estimate() -> None:
    result = analyze_assessment(_inputs(market_estimate=None))
    assert result.status == "unknown"
    assert result.gap is None
    assert result.confidence == "low"


def test_unknown_without_assessment() -> None:
    result = analyze_assessment(_inputs(assessed_market_value=None))
    assert result.status == "unknown"


def test_zero_assessment_is_unknown_not_division_error() -> None:
    result = analyze_assessment(_inputs(assessed_market_value=0.0))
    assert result.status == "unknown"


def test_confidence_carries_from_valuation() -> None:
    result = analyze_assessment(
        _inputs(
            assessed_market_value=300000.0,
            market_estimate=200000.0,
            valuation_confidence="low",
        )
    )
    assert result.confidence == "low"
    assert any("low-confidence" in reason for reason in result.reasons)


def test_tax_rate_is_reported() -> None:
    result = analyze_assessment(_inputs())
    assert result.tax_rate == PHILADELPHIA_REALTY_TAX_RATE
