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
        "is_vacant": True,
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


def test_a_developed_parcel_gets_no_appeal_figure() -> None:
    analysis = analyze_assessment(
        AssessmentInputs(
            assessed_market_value=200_000.0,
            market_estimate=40_000.0,
            market_low=30_000.0,
            market_high=50_000.0,
            valuation_confidence="medium",
            is_vacant=False,
        )
    )
    assert analysis.status == "unknown"
    assert analysis.over_assessed_amount is None
    assert analysis.estimated_annual_tax_savings is None
    assert analysis.confidence == "low"
    assert any("vacant" in reason.lower() for reason in analysis.reasons)


def test_a_vacant_parcel_still_gets_its_appeal_figure() -> None:
    analysis = analyze_assessment(
        AssessmentInputs(
            assessed_market_value=200_000.0,
            market_estimate=40_000.0,
            market_low=30_000.0,
            market_high=50_000.0,
            valuation_confidence="medium",
            is_vacant=True,
        )
    )
    assert analysis.status == "over_assessed"
    assert analysis.over_assessed_amount == 160_000.0
    assert analysis.estimated_annual_tax_savings is not None


def test_unknown_vacancy_is_treated_as_not_provable() -> None:
    analysis = analyze_assessment(
        AssessmentInputs(
            assessed_market_value=200_000.0,
            market_estimate=40_000.0,
            market_low=30_000.0,
            market_high=50_000.0,
            valuation_confidence="medium",
            is_vacant=None,
        )
    )
    assert analysis.status == "unknown"
    assert analysis.estimated_annual_tax_savings is None


def test_a_developed_parcel_says_why_even_with_no_comp_data() -> None:
    analysis = analyze_assessment(
        AssessmentInputs(
            assessed_market_value=200_000.0,
            market_estimate=None,
            market_low=None,
            market_high=None,
            valuation_confidence=None,
            is_vacant=False,
        )
    )
    assert analysis.status == "unknown"
    assert analysis.estimated_annual_tax_savings is None
    assert any("vacant" in reason.lower() for reason in analysis.reasons)
    assert not any("not enough" in reason.lower() for reason in analysis.reasons)
