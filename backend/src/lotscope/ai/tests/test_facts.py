from datetime import UTC, datetime
from typing import Any

from lotscope.ai.prompts import SUMMARY_SYSTEM_PROMPT
from lotscope.ai.service import _data_coverage, _report_facts, _summary_facts
from lotscope.parcels.schemas import ParcelDetail
from lotscope.verdict.schemas import VerdictResult

_NOW = datetime(2026, 7, 4, tzinfo=UTC)


def _detail(**overrides: Any) -> ParcelDetail:
    base: dict[str, Any] = dict.fromkeys(ParcelDetail.model_fields)
    base["parcel_number"] = "000000001"
    base.update(overrides)
    base["market_code"] = "phl"
    base["local_key"] = str(base["parcel_number"]).split(":")[-1]
    return ParcelDetail(**base)


def _verdict(**overrides: Any) -> VerdictResult:
    base: dict[str, Any] = {
        "parcel_number": "000000001",
        "verdict_version": "v8",
        "buildability_score": 70.0,
        "opportunity_score": 68.0,
        "summary": "RSA-5: buildable by-right.",
        "can_build_by_right": True,
        "by_right_units": 1,
        "max_height_ft": 38.0,
        "needs_variance": False,
        "buildable_area_sqft": 1557.0,
        "value_estimate_low": 7929.0,
        "value_estimate_high": 72261.0,
        "value_confidence": 0.3,
        "assessment_market_gap": None,
        "arv": 97500.0,
        "est_profit": -535041.0,
        "est_margin": -5.4876,
        "max_allowable_offer": 0.0,
        "deal_score": 0.0,
        "is_underpriced": False,
        "risk_score": 80.0,
        "risk_flags": [],
        "sources": [],
        "computed_at": _NOW,
    }
    base.update(overrides)
    return VerdictResult(**base)


def test_infeasible_deal_is_narrated_not_quoted_as_negative() -> None:
    facts = _report_facts(_detail(), _verdict(), None, None, "RSA-5")
    assert "not economically feasible" in facts.lower()
    assert "-535041" not in facts
    assert "-5.4876" not in facts


def test_infeasible_detected_from_legacy_negative_mao() -> None:
    facts = _summary_facts(_detail(), _verdict(max_allowable_offer=-532575.0), None, None)
    assert "not economically feasible" in facts.lower()
    assert "-532575" not in facts


def test_feasible_deal_still_reports_numbers() -> None:
    verdict = _verdict(
        max_allowable_offer=95000.0, deal_score=62.0, is_underpriced=True, est_margin=0.15
    )
    facts = _report_facts(_detail(), verdict, None, None, "RSA-5")
    assert "95000" in facts
    assert "not economically feasible" not in facts.lower()


def test_summary_prompt_carries_score_legend() -> None:
    assert "SCORE LEGEND" in SUMMARY_SYSTEM_PROMPT
    assert "NOT a motivated seller" in SUMMARY_SYSTEM_PROMPT
    assert "underpriced rating of False" in SUMMARY_SYSTEM_PROMPT


def test_data_coverage_is_low_without_engine_outputs() -> None:
    assert _data_coverage(None, None) == "low"


def test_data_coverage_rises_with_verdict_and_comps() -> None:
    assert _data_coverage(_verdict(value_estimate_low=100000.0), None) == "medium"


def test_snapshot_uses_resolved_district_when_attribute_is_null() -> None:
    facts = _summary_facts(
        _detail(base_zoning_code=None, resolved_zoning_code="RM", zoning_resolution="spatial"),
        _verdict(),
        None,
        None,
    )
    assert "Zoning: RM" in facts
    assert "Zoning: unknown" not in facts


def test_snapshot_keeps_attribute_zoning_for_phl_unchanged() -> None:
    facts = _summary_facts(
        _detail(base_zoning_code="RSA5", resolved_zoning_code="RSA5", zoning_resolution="attribute"),
        _verdict(),
        None,
        None,
    )
    assert "Zoning: RSA5" in facts


def test_snapshot_carries_risk_coverage_for_hbg_not_phl() -> None:
    hbg = _detail()
    hbg.market_code = "hbg"
    facts_hbg = _summary_facts(hbg, _verdict(risk_score=0.0, risk_flags=[]), None, None)
    assert "Risk coverage" in facts_hbg
    facts_phl = _summary_facts(_detail(), _verdict(risk_score=0.0, risk_flags=[]), None, None)
    assert "Risk coverage" not in facts_phl


def test_summary_prompt_forbids_invented_risk() -> None:
    from lotscope.ai.prompts import SUMMARY_SYSTEM_PROMPT

    assert "risk score is 0" in SUMMARY_SYSTEM_PROMPT
    assert "invent offsetting" in SUMMARY_SYSTEM_PROMPT


def test_assessed_value_fact_labels_base_year_market() -> None:
    from lotscope.ai.service import _assessed_value_fact

    hbg = _assessed_value_fact(_detail(market_value=2300.0, assessment_ratio=0.4042))
    assert "common level ratio" in hbg
    assert "NOT market value" in hbg
    assert "5690" in hbg or "5691" in hbg
    phl = _assessed_value_fact(_detail(market_value=510000.0, assessment_ratio=1.0))
    assert phl == "Assessed value: 510000.0."
