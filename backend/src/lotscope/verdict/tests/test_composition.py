from datetime import datetime

from lotscope.risk.schemas import RiskFlagSchema, RiskResult
from lotscope.valuation.schemas import ValuationResult
from lotscope.verdict.composition import VERDICT_VERSION, compose_verdict
from lotscope.zoning.schemas import BuildabilityResult

_NOW = datetime(2024, 1, 1)


def _buildability(**overrides: object) -> BuildabilityResult:
    base: dict[str, object] = {
        "parcel_number": "1",
        "district_code": "RSA-5",
        "district_method": "spatial",
        "cited_section": "RSA-5 (Title 14, v)",
        "conforming": True,
        "can_build_by_right": True,
        "needs_variance": False,
        "by_right_units": 1,
        "max_height_ft": 38.0,
        "buildable_area_sqft": 1400.0,
        "buildability_score": 80.0,
        "confidence": "high",
        "reasons": [],
        "sources": [{"source": "zoning_standard"}],
        "computed_at": _NOW,
    }
    base.update(overrides)
    return BuildabilityResult(**base)


def _valuation(**overrides: object) -> ValuationResult:
    base: dict[str, object] = {
        "parcel_number": "1",
        "estimate": 200000.0,
        "low": 180000.0,
        "high": 220000.0,
        "price_per_sqft": 100.0,
        "confidence": "high",
        "comp_count": 5,
        "coefficient_of_variation": 0.1,
        "comps": [],
        "reasons": [],
        "sources": [{"source": "rtt_summary"}],
        "computed_at": _NOW,
    }
    base.update(overrides)
    return ValuationResult(**base)


def _risk(flags: list[RiskFlagSchema] | None = None, score: float = 20.0) -> RiskResult:
    return RiskResult(
        parcel_number="1",
        risk_score=score,
        flags=flags or [],
        summary="",
        confidence="high",
        sources=[{"source": "tax_status"}],
        computed_at=_NOW,
    )


def test_full_compose_maps_all_dimensions() -> None:
    flag = RiskFlagSchema(
        code="flood_zone", severity="high", label="Flood", detail="AE", source="flood_zone"
    )
    verdict = compose_verdict(
        _buildability(), _valuation(), _risk([flag]), assessed_market_value=150000.0
    )
    assert verdict.verdict_version == VERDICT_VERSION
    assert verdict.buildability_score == 80.0
    assert verdict.can_build_by_right is True
    assert verdict.by_right_units == 1
    assert verdict.value_estimate_low == 180000.0
    assert verdict.value_confidence == 0.9
    assert verdict.assessment_market_gap == 50000.0
    assert verdict.risk_score == 20.0
    assert verdict.risk_flags[0]["code"] == "flood_zone"
    assert len(verdict.sources) == 3


def test_opportunity_score_blends_buildability_and_risk() -> None:
    verdict = compose_verdict(
        _buildability(buildability_score=80.0),
        _valuation(),
        _risk(score=20.0),
        assessed_market_value=None,
    )
    assert verdict.opportunity_score == 80.0


def test_summary_reads_naturally() -> None:
    verdict = compose_verdict(_buildability(), _valuation(), _risk(), assessed_market_value=None)
    assert "RSA-5: buildable by-right (1 unit)" in verdict.summary
    assert "est. $180,000-$220,000" in verdict.summary
    assert "no major risk flags" in verdict.summary


def test_missing_dimensions_are_none() -> None:
    verdict = compose_verdict(None, None, None, assessed_market_value=None)
    assert verdict.buildability_score is None
    assert verdict.value_estimate_low is None
    assert verdict.risk_score is None
    assert verdict.risk_flags == []
    assert verdict.summary == "Insufficient data for a verdict."
    assert verdict.opportunity_score == 40.0


def test_gap_requires_estimate_and_assessment() -> None:
    no_estimate = compose_verdict(
        _buildability(), _valuation(estimate=None), _risk(), assessed_market_value=150000.0
    )
    assert no_estimate.assessment_market_gap is None
