from datetime import datetime

from lotscope.deal.schemas import DealAssumptionsSchema, DealResult
from lotscope.risk.schemas import RiskFlagSchema, RiskResult
from lotscope.valuation.schemas import ValuationResult
from lotscope.verdict.composition import compose_verdict
from lotscope.zoning.schemas import BuildabilityResult

_NOW = datetime(2024, 1, 1)


def _deal(**overrides: object) -> DealResult:
    base: dict[str, object] = {
        "parcel_number": "1",
        "units": 2,
        "arv": 600000.0,
        "per_unit_value": 300000.0,
        "gross_floor_area_sqft": 2400.0,
        "acquisition_cost": 80000.0,
        "construction_cost": 420000.0,
        "soft_cost": 63000.0,
        "selling_cost": 42000.0,
        "total_cost": 605000.0,
        "profit": -5000.0,
        "margin": -0.0083,
        "roi": -0.0087,
        "max_allowable_offer": 75000.0,
        "is_underpriced": False,
        "deal_score": 48.0,
        "comp_count": 6,
        "confidence": "high",
        "assumptions": DealAssumptionsSchema(
            construction_cost_per_sqft=175.0,
            soft_cost_pct=0.15,
            selling_cost_pct=0.07,
            target_margin=0.2,
            default_unit_sqft=1200.0,
            max_unit_sqft=3000.0,
        ),
        "reasons": [],
        "sources": [{"dimension": "deal"}],
        "computed_at": _NOW,
    }
    base.update(overrides)
    return DealResult(**base)


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
    assert verdict.buildability_score == 80.0
    assert verdict.can_build_by_right is True
    assert verdict.by_right_units == 1
    assert verdict.value_estimate_low == 180000.0
    assert verdict.value_confidence == 0.9
    assert verdict.assessment_market_gap == 50000.0
    assert verdict.risk_score == 20.0
    assert verdict.risk_flags[0]["code"] == "flood_zone"
    assert len(verdict.sources) == 3


def test_opportunity_score_scales_the_blend_by_the_deal_economics() -> None:
    strong = compose_verdict(
        _buildability(buildability_score=80.0),
        _valuation(),
        _risk(score=20.0),
        _deal(margin=0.25, profit=150000.0),
        assessed_market_value=None,
    )
    assert strong.opportunity_score == 80.0


def test_an_unprofitable_deal_cannot_score_as_an_opportunity() -> None:
    losing = compose_verdict(
        _buildability(buildability_score=80.0),
        _valuation(),
        _risk(score=20.0),
        _deal(margin=-0.15, profit=-90000.0),
        assessed_market_value=None,
    )
    assert losing.opportunity_score == 32.0


def test_an_infeasible_deal_scores_at_the_economics_floor() -> None:
    infeasible = compose_verdict(
        _buildability(buildability_score=80.0),
        _valuation(),
        _risk(score=20.0),
        _deal(infeasible=True, margin=None, profit=None),
        assessed_market_value=None,
    )
    assert infeasible.opportunity_score == 32.0


def test_unknown_economics_is_treated_as_just_viable_not_as_strong() -> None:
    unknown = compose_verdict(
        _buildability(buildability_score=80.0),
        _valuation(),
        _risk(score=20.0),
        None,
        assessed_market_value=None,
    )
    strong = compose_verdict(
        _buildability(buildability_score=80.0),
        _valuation(),
        _risk(score=20.0),
        _deal(margin=0.25, profit=150000.0),
        assessed_market_value=None,
    )
    losing = compose_verdict(
        _buildability(buildability_score=80.0),
        _valuation(),
        _risk(score=20.0),
        _deal(margin=-0.15, profit=-90000.0),
        assessed_market_value=None,
    )

    assert losing.opportunity_score < unknown.opportunity_score < strong.opportunity_score
    assert unknown.opportunity_score == 56.0


def test_a_pass_recommendation_never_outranks_an_investigate_one() -> None:
    unattractive = compose_verdict(
        _buildability(buildability_score=95.0),
        _valuation(),
        _risk(score=5.0),
        _deal(margin=-0.20, profit=-120000.0),
        assessed_market_value=None,
    )
    investigate = compose_verdict(
        _buildability(buildability_score=60.0),
        _valuation(),
        _risk(score=40.0),
        _deal(margin=0.22, profit=140000.0),
        assessed_market_value=None,
    )

    assert unattractive.recommendation == "economics_unattractive"
    assert unattractive.opportunity_score < investigate.opportunity_score


def test_summary_reads_naturally() -> None:
    verdict = compose_verdict(_buildability(), _valuation(), _risk(), assessed_market_value=None)
    assert "RSA-5: buildable by-right (1 unit)" in verdict.summary
    assert "est. $180,000-$220,000" in verdict.summary
    assert "no major risk flags" in verdict.summary


def test_summary_pluralises_the_by_right_unit_count() -> None:
    single = compose_verdict(
        _buildability(by_right_units=1), None, None, assessed_market_value=None
    )
    assert "(1 unit)" in single.summary

    several = compose_verdict(
        _buildability(by_right_units=4), None, None, assessed_market_value=None
    )
    assert "(4 units)" in several.summary


def test_summary_flags_master_plan_for_special_purpose() -> None:
    verdict = compose_verdict(
        _buildability(
            district_code="SP-INS",
            requires_master_plan=True,
            can_build_by_right=False,
            by_right_units=None,
        ),
        None,
        _risk(),
        assessed_market_value=None,
    )
    assert "SP-INS: master plan required" in verdict.summary
    assert "buildable by-right" not in verdict.summary
    assert verdict.can_build_by_right is False


def test_missing_dimensions_are_none() -> None:
    verdict = compose_verdict(None, None, None, assessed_market_value=None)
    assert verdict.buildability_score is None
    assert verdict.value_estimate_low is None
    assert verdict.risk_score is None
    assert verdict.risk_flags == []
    assert verdict.summary == "Insufficient data for a verdict."
    assert verdict.opportunity_score == 28.0


def test_gap_requires_estimate_and_assessment() -> None:
    no_estimate = compose_verdict(
        _buildability(), _valuation(estimate=None), _risk(), assessed_market_value=150000.0
    )
    assert no_estimate.assessment_market_gap is None


def test_deal_dimension_maps_into_verdict() -> None:
    verdict = compose_verdict(
        _buildability(), _valuation(), _risk(), _deal(), assessed_market_value=None
    )
    assert verdict.arv == 600000.0
    assert verdict.est_profit == -5000.0
    assert verdict.max_allowable_offer == 75000.0
    assert verdict.deal_score == 48.0
    assert verdict.is_underpriced is False
    assert any(source["dimension"] == "deal" for source in verdict.sources)
    assert "MAO $75,000" in verdict.summary


def test_underpriced_deal_is_called_out_in_summary() -> None:
    verdict = compose_verdict(
        _buildability(),
        _valuation(),
        _risk(),
        _deal(is_underpriced=True, max_allowable_offer=140000.0),
        assessed_market_value=None,
    )
    assert "MAO $140,000 (underpriced)" in verdict.summary


def test_infeasible_deal_replaces_mao_in_summary() -> None:
    verdict = compose_verdict(
        _buildability(),
        _valuation(),
        _risk(),
        _deal(infeasible=True, max_allowable_offer=0.0, is_underpriced=False),
        assessed_market_value=None,
    )
    assert "no land price reaches the target margin" in verdict.summary
    assert "MAO $" not in verdict.summary


def test_deal_fields_default_to_none_without_deal() -> None:
    verdict = compose_verdict(_buildability(), _valuation(), _risk(), assessed_market_value=None)
    assert verdict.arv is None
    assert verdict.max_allowable_offer is None
    assert verdict.deal_score is None
    assert verdict.is_underpriced is None


def test_field_trust_marks_absent_dimensions_unavailable_not_clean() -> None:
    composed = compose_verdict(None, None, None, None, assessed_market_value=None)
    assert composed.field_trust
    for name, provenance in composed.field_trust.items():
        assert provenance.status == "unavailable", name
        assert provenance.limitations, name


def test_field_trust_never_reports_verified_for_a_derived_conclusion() -> None:
    composed = compose_verdict(None, None, None, None, assessed_market_value=None)
    assert all(p.status != "verified" for p in composed.field_trust.values())


def test_field_trust_covers_every_material_field() -> None:
    composed = compose_verdict(None, None, None, None, assessed_market_value=None)
    assert set(composed.field_trust) == {
        "can_build_by_right",
        "by_right_units",
        "max_height_ft",
        "buildable_area_sqft",
        "value_estimate_low",
        "value_estimate_high",
        "assessment_market_gap",
        "arv",
        "est_profit",
        "est_margin",
        "max_allowable_offer",
    }
