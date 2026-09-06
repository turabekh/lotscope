"""The claims the stored-verdict invariants used to scan a table for.

They were checks on 588,000 rows of a table that no longer exists, run nightly, which
could only ever report a contradiction after it had been served to somebody. They are
properties of the composition, so they are asserted here, where a breach fails the build
instead of a cron.
"""

from datetime import datetime

from lotscope.deal.schemas import DealAssumptionsSchema, DealResult
from lotscope.risk.schemas import RiskFlagSchema, RiskResult
from lotscope.valuation.schemas import ValuationResult
from lotscope.verdict.composition import compose_verdict
from lotscope.zoning.schemas import BuildabilityResult

_NOW = datetime(2026, 1, 1)


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
        "profit": 120000.0,
        "margin": 0.25,
        "roi": 0.3,
        "max_allowable_offer": 75000.0,
        "is_underpriced": True,
        "deal_score": 80.0,
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


def _risk(score: float = 20.0, flags: list[RiskFlagSchema] | None = None) -> RiskResult:
    return RiskResult(
        parcel_number="1",
        risk_score=score,
        flags=flags or [],
        summary="",
        confidence="high",
        sources=[{"source": "tax_status"}],
        computed_at=_NOW,
    )


# A single example proves nothing about a claim quantified over every parcel, so each
# claim below sweeps the inputs it is quantified over. Profit is derived from the margin
# rather than varied independently, because it is derived that way in the deal too — a
# sweep that pairs a 20% margin with a six-figure loss tests a state the system cannot
# reach and fails on its own arithmetic, not on the claim.
_TOTAL_COST = 605000.0
_MARGINS = (-0.40, -0.08, -0.001, 0.0, 0.05, 0.10, 0.12, 0.199, 0.20, 0.35)
_RISKS = (0.0, 30.0, 59.0, 60.0, 90.0)


def _coherent_deal(margin: float, **overrides: object) -> DealResult:
    profit = round(margin * _TOTAL_COST, 2)
    return _deal(profit=profit, margin=margin, roi=profit / _TOTAL_COST, **overrides)


def _sweep() -> list[tuple[float, float]]:
    return [(margin, risk) for margin in _MARGINS for risk in _RISKS]


def test_a_strong_candidate_never_loses_money() -> None:
    for margin, risk in _sweep():
        verdict = compose_verdict(
            _buildability(),
            _valuation(),
            _risk(score=risk),
            _coherent_deal(margin),
            assessed_market_value=150000.0,
        )
        if verdict.recommendation == "strong_candidate":
            assert verdict.est_profit is not None
            assert verdict.est_profit >= 0, (margin, risk)


def test_a_viable_margin_making_money_is_not_called_economically_unattractive() -> None:
    for margin, risk in _sweep():
        verdict = compose_verdict(
            _buildability(),
            _valuation(),
            _risk(score=risk),
            _coherent_deal(margin),
            assessed_market_value=150000.0,
        )
        if margin >= 0.10:
            assert verdict.recommendation != "economics_unattractive", (margin, risk)


def test_a_by_right_parcel_is_never_screened_as_an_entitlement_risk() -> None:
    for margin, risk in _sweep():
        verdict = compose_verdict(
            _buildability(can_build_by_right=True, needs_variance=False),
            _valuation(),
            _risk(score=risk),
            _coherent_deal(margin),
            assessed_market_value=150000.0,
        )
        assert verdict.recommendation != "high_entitlement_risk", (margin, risk)


def test_a_by_right_parcel_never_also_needs_a_variance() -> None:
    for by_right, needs_variance in ((True, False), (False, True), (False, False)):
        verdict = compose_verdict(
            _buildability(can_build_by_right=by_right, needs_variance=needs_variance),
            _valuation(),
            _risk(),
            _deal(),
            assessed_market_value=150000.0,
        )
        assert not (verdict.can_build_by_right and verdict.needs_variance)


def test_an_infeasible_build_is_never_a_strong_candidate_at_the_target_margin() -> None:
    # Max allowable offer of nothing means the build cannot reach the target margin even
    # with free land, so calling it strong would be a contradiction.
    for margin, risk in _sweep():
        verdict = compose_verdict(
            _buildability(),
            _valuation(),
            _risk(score=risk),
            _coherent_deal(margin, max_allowable_offer=0.0),
            assessed_market_value=150000.0,
        )
        if verdict.max_allowable_offer == 0.0 and verdict.recommendation == "strong_candidate":
            assert verdict.est_margin is not None
            assert verdict.est_margin >= 0.20, (margin, risk)
