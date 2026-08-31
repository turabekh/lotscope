from typing import Any

from lotscope.core.provenance import calculated, estimated, unavailable
from lotscope.verdict.decision import (
    DEAL_KILLER_LIMIT,
    ELEVATED_RISK_SCORE,
    STRONG_MARGIN,
    VIABLE_MARGIN,
    ScreeningDecision,
    decide,
    rank_deal_killers,
)

_KNOWN = {
    "can_build_by_right": calculated("zoning_district"),
    "by_right_units": calculated("zoning_district"),
}


def _decide(**kw: Any) -> ScreeningDecision:
    args: dict[str, Any] = {
        "field_trust": _KNOWN,
        "can_build_by_right": True,
        "needs_variance": False,
        "requires_master_plan": False,
        "est_margin": STRONG_MARGIN + 0.05,
        "deal_infeasible": False,
        "risk_score": 10.0,
    }
    args.update(kw)
    return decide(**args)


def test_a_clean_parcel_is_a_strong_candidate() -> None:
    assert _decide().recommendation == "strong_candidate"


def test_an_unavailable_critical_field_forces_insufficient_data() -> None:
    result = _decide(
        field_trust={
            "can_build_by_right": unavailable("No district resolved."),
            "by_right_units": calculated("zoning_district"),
        }
    )
    assert result.recommendation == "insufficient_data"
    assert "can_build_by_right" in result.reason


def test_a_missing_critical_field_forces_insufficient_data() -> None:
    assert _decide(field_trust={}).recommendation == "insufficient_data"


def test_attractive_economics_cannot_override_a_critical_unknown() -> None:
    result = _decide(
        field_trust={"can_build_by_right": unavailable("Not evaluated.")},
        est_margin=0.95,
        risk_score=0.0,
    )
    assert result.recommendation == "insufficient_data"


def test_a_master_plan_requirement_is_entitlement_risk() -> None:
    assert _decide(requires_master_plan=True).recommendation == "high_entitlement_risk"


def test_a_master_plan_requirement_outranks_attractive_economics() -> None:
    result = _decide(requires_master_plan=True, est_margin=0.9)
    assert result.recommendation == "high_entitlement_risk"


def test_a_variance_path_is_entitlement_risk() -> None:
    result = _decide(can_build_by_right=False, needs_variance=True)
    assert result.recommendation == "high_entitlement_risk"


def test_an_infeasible_build_with_no_margin_is_unattractive() -> None:
    assert _decide(deal_infeasible=True, est_margin=None).recommendation == "economics_unattractive"


def test_an_infeasible_build_below_the_viable_bar_is_unattractive() -> None:
    result = _decide(deal_infeasible=True, est_margin=VIABLE_MARGIN - 0.02)

    assert result.recommendation == "economics_unattractive"
    assert "land price of $0" in result.reason


def test_an_infeasible_build_that_still_clears_the_viable_bar_is_investigated() -> None:
    result = _decide(deal_infeasible=True, est_margin=0.13)

    assert result.recommendation == "worth_investigating"
    assert "13%" in result.reason
    assert "target margin at any land price" in result.reason


def test_a_thin_margin_is_unattractive() -> None:
    result = _decide(est_margin=VIABLE_MARGIN - 0.01)
    assert result.recommendation == "economics_unattractive"


def test_the_viable_margin_boundary_is_not_unattractive() -> None:
    assert _decide(est_margin=VIABLE_MARGIN).recommendation != "economics_unattractive"


def test_elevated_risk_downgrades_a_strong_margin_to_investigate() -> None:
    result = _decide(est_margin=STRONG_MARGIN + 0.1, risk_score=ELEVATED_RISK_SCORE)
    assert result.recommendation == "worth_investigating"


def test_a_middling_margin_is_worth_investigating() -> None:
    result = _decide(est_margin=(VIABLE_MARGIN + STRONG_MARGIN) / 2)
    assert result.recommendation == "worth_investigating"


def test_an_ineligible_parcel_without_a_variance_path_is_a_likely_pass() -> None:
    result = _decide(can_build_by_right=False, needs_variance=False)
    assert result.recommendation == "likely_pass"


def test_unknown_economics_do_not_manufacture_an_unattractive_verdict() -> None:
    assert _decide(est_margin=None).recommendation == "worth_investigating"


def test_every_decision_states_a_reason() -> None:
    cases: list[dict[str, Any]] = [
        {},
        {"requires_master_plan": True},
        {"deal_infeasible": True},
        {"field_trust": {}},
        {"can_build_by_right": False, "needs_variance": False},
    ]
    for kw in cases:
        assert _decide(**kw).reason.strip()


def test_deal_killers_rank_by_severity_then_decision_impact() -> None:
    flags: list[dict[str, Any]] = [
        {"code": "historic_district", "severity": "high"},
        {"code": "no_street_access", "severity": "high"},
        {"code": "flood_zone", "severity": "low"},
        {"code": "tax_delinquent", "severity": "medium"},
    ]
    ranked = rank_deal_killers(flags)
    assert [f["code"] for f in ranked] == [
        "no_street_access",
        "historic_district",
        "tax_delinquent",
    ]


def test_deal_killers_are_capped_and_nothing_is_invented() -> None:
    flags: list[dict[str, Any]] = [{"code": f"c{i}", "severity": "high"} for i in range(10)]
    assert len(rank_deal_killers(flags)) == DEAL_KILLER_LIMIT
    assert rank_deal_killers([]) == []


def test_ranking_is_deterministic_for_equal_severity_and_impact() -> None:
    flags: list[dict[str, Any]] = [
        {"code": "b_code", "severity": "low"},
        {"code": "a_code", "severity": "low"},
    ]
    assert [f["code"] for f in rank_deal_killers(flags)] == ["a_code", "b_code"]


def test_an_estimated_field_is_not_treated_as_a_critical_unknown() -> None:
    result = _decide(
        field_trust={
            "can_build_by_right": calculated("zoning_district"),
            "by_right_units": estimated("zoning_district", confidence="low"),
        }
    )
    assert result.recommendation == "strong_candidate"


def test_a_strong_margin_on_an_assessed_land_value_is_only_worth_investigating() -> None:
    result = _decide(land_value_modelled=False)
    assert result.recommendation == "worth_investigating"
    assert "rests on the assessed value" in result.reason
    assert "no comparable land sales" in result.reason


def test_a_strong_margin_on_a_modelled_land_value_still_stands() -> None:
    assert _decide(land_value_modelled=True).recommendation == "strong_candidate"


def test_the_strong_reason_names_the_flags_it_sits_beside() -> None:
    result = _decide(risk_score=30.0, risk_flag_count=3)
    assert result.recommendation == "strong_candidate"
    assert "3 flags recorded" in result.reason
    assert "no elevated risk signal" not in result.reason
    assert "review them before committing" in result.reason


def test_a_single_flag_reads_in_the_singular() -> None:
    assert "1 flag recorded" in _decide(risk_score=20.0, risk_flag_count=1).reason


def test_a_clean_parcel_says_no_flags_rather_than_no_elevated_signal() -> None:
    result = _decide(risk_flag_count=0)
    assert "no risk flags recorded" in result.reason
    assert "no elevated risk signal" not in result.reason


def test_the_assessed_downgrade_does_not_override_an_earlier_rule() -> None:
    infeasible = _decide(land_value_modelled=False, deal_infeasible=True, est_margin=None)
    assert infeasible.recommendation == "economics_unattractive"

    variance = _decide(land_value_modelled=False, can_build_by_right=False, needs_variance=True)
    assert variance.recommendation == "high_entitlement_risk"


def test_wide_area_land_value_does_not_earn_strong_candidate() -> None:
    result = _decide(est_margin=0.55, risk_score=10.0, land_value_is_wide_area=True)

    assert result.recommendation == "worth_investigating"
    assert "wider search" in result.reason
    assert "rough guide" in result.reason


def test_wide_area_reason_is_distinct_from_the_assessed_fallback() -> None:
    wide = _decide(est_margin=0.55, risk_score=10.0, land_value_is_wide_area=True)
    assessed = _decide(est_margin=0.55, risk_score=10.0, land_value_modelled=False)

    assert wide.reason != assessed.reason
    assert "assessed value" in assessed.reason
    assert "assessed value" not in wide.reason


def test_local_land_value_still_earns_strong_candidate() -> None:
    result = _decide(est_margin=0.55, risk_score=10.0, land_value_is_wide_area=False)

    assert result.recommendation == "strong_candidate"


def test_a_wide_area_estimate_cannot_rescue_infeasible_economics() -> None:
    result = _decide(
        deal_infeasible=True, est_margin=VIABLE_MARGIN - 0.05, land_value_is_wide_area=True
    )

    assert result.recommendation == "economics_unattractive"


def test_a_master_plan_district_is_screened_not_reported_as_unknown() -> None:
    decision = decide(
        field_trust={},
        can_build_by_right=False,
        needs_variance=None,
        requires_master_plan=True,
        est_margin=None,
        deal_infeasible=False,
        risk_score=None,
    )

    assert decision.recommendation == "high_entitlement_risk"
    assert "master plan" in decision.reason
    assert "could not be established" not in decision.reason


def test_missing_buildability_still_reports_insufficient_data_without_a_master_plan() -> None:
    decision = decide(
        field_trust={},
        can_build_by_right=None,
        needs_variance=None,
        requires_master_plan=False,
        est_margin=None,
        deal_infeasible=False,
        risk_score=None,
    )

    assert decision.recommendation == "insufficient_data"


def test_an_ineligible_parcel_stays_a_likely_pass_whatever_the_economics() -> None:
    for est_margin in (None, VIABLE_MARGIN - 0.05, STRONG_MARGIN + 0.1):
        result = _decide(can_build_by_right=False, needs_variance=False, est_margin=est_margin)
        assert result.recommendation == "likely_pass"


def test_an_ineligible_parcel_stays_a_likely_pass_when_no_land_price_works() -> None:
    result = _decide(
        can_build_by_right=False,
        needs_variance=False,
        est_margin=None,
        deal_infeasible=True,
    )
    assert result.recommendation == "likely_pass"
