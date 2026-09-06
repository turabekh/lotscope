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
    assert "target margin at any land price" in facts.lower()
    assert "-535041" not in facts
    assert "-5.4876" not in facts


def test_infeasible_detected_from_legacy_negative_mao() -> None:
    facts = _summary_facts(_detail(), _verdict(max_allowable_offer=-532575.0), None, None)
    assert "target margin at any land price" in facts.lower()
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
        _detail(
            base_zoning_code="RSA5", resolved_zoning_code="RSA5", zoning_resolution="attribute"
        ),
        _verdict(),
        None,
        None,
    )
    assert "Zoning: RSA5" in facts


def test_summary_prompt_forbids_invented_risk() -> None:
    from lotscope.ai.prompts import SUMMARY_SYSTEM_PROMPT

    assert "risk score is 0" in SUMMARY_SYSTEM_PROMPT
    assert "invent offsetting" in SUMMARY_SYSTEM_PROMPT


def test_assessed_value_fact_states_the_philadelphia_assessment_directly() -> None:
    from lotscope.ai.service import _assessed_value_fact

    phl = _assessed_value_fact(_detail(market_value=510000.0, assessment_ratio=1.0))
    assert phl == "Assessed value: 510000.0."


def _flagship_flags() -> list[dict[str, Any]]:
    return [
        {
            "code": "tax_delinquency",
            "severity": "info",
            "label": "Tax delinquency recorded against a prior owner",
            "detail": (
                "$8,975 owed over 44 year(s). Recorded as of 2022-06 against MATUSOW JOSEPH, "
                "the prior owner named as grantor on the 2025-05-08 sheriff's deed "
                "(doc 54420482). Debt predates the current owner and is likely discharged at "
                "sheriff sale — verify with the Dept. of Revenue."
            ),
            "source": "tax_status",
        },
        {
            "code": "li_violations",
            "severity": "low",
            "label": "L&I violations on record",
            "detail": "1 violation(s) on record — Vacant Structure & Land.",
            "source": "li_event",
        },
    ]


def test_snapshot_payload_carries_flag_severity_and_detail() -> None:
    from lotscope.ai.service import _summary_facts

    facts = _summary_facts(_detail(), _verdict(risk_flags=_flagship_flags()), None, None)

    assert "informational context, not a live burden on the current owner" in facts
    assert "the prior owner named as grantor on the 2025-05-08 sheriff's deed" in facts
    assert "1 violation(s) on record" in facts


def test_snapshot_payload_splits_open_from_on_record_violations() -> None:
    from lotscope.ai.service import _summary_facts
    from lotscope.risk.schemas import ViolationPosture

    complied = _summary_facts(
        _detail(),
        _verdict(risk_flags=_flagship_flags()),
        None,
        None,
        ViolationPosture(parcel_number="000000001", violations_on_record=1, open_violations=0),
    )
    assert "1 on record, 0 currently open" in complied
    assert "complied with or closed" in complied
    assert "This is history, not an active violation." in complied

    live = _summary_facts(
        _detail(),
        _verdict(risk_flags=_flagship_flags()),
        None,
        None,
        ViolationPosture(parcel_number="000000001", violations_on_record=3, open_violations=2),
    )
    assert "3 on record, 2 currently open and unresolved" in live
    assert "history" not in live.lower()


def test_snapshot_payload_names_distress_signals_as_present_and_additive() -> None:
    from lotscope.ai.service import _summary_facts
    from lotscope.distress.schemas import DistressFactor, DistressResult

    distress = DistressResult(
        parcel_number="000000001",
        score=20,
        tier="low",
        version="v2",
        profile_id="philly-distress-v2",
        factors=[
            DistressFactor(code="vacant", label="Vacant lot — owner unlikely to occupy", weight=10),
            DistressFactor(
                code="absentee", label="Absentee owner (out-of-area mailing address)", weight=10
            ),
        ],
        sources=[],
        computed_at=_NOW,
    )
    facts = _summary_facts(_detail(), _verdict(), distress, None)

    assert "Distress score 20/100 (low)" in facts
    assert "Vacant lot — owner unlikely to occupy (+10)" in facts
    assert "Absentee owner (out-of-area mailing address) (+10)" in facts
    assert "No other distress signal was found on this parcel." in facts
    assert "signals PRESENT on this parcel" in facts


def test_snapshot_payload_is_honest_when_distress_factors_are_truncated() -> None:
    from lotscope.ai.service import _DISTRESS_FACTOR_LIMIT, _summary_facts
    from lotscope.distress.schemas import DistressFactor, DistressResult

    factors = [
        DistressFactor(code=f"c{index}", label=f"Signal {index}", weight=5)
        for index in range(_DISTRESS_FACTOR_LIMIT + 2)
    ]
    distress = DistressResult(
        parcel_number="000000001",
        score=30,
        tier="medium",
        version="v2",
        profile_id="philly-distress-v2",
        factors=factors,
        sources=[],
        computed_at=_NOW,
    )
    facts = _summary_facts(_detail(), _verdict(), distress, None)

    assert f"largest of {len(factors)} signals present" in facts
    assert "No other distress signal was found" not in facts


def test_summary_prompt_forbids_calling_a_complied_violation_active() -> None:
    assert "ONLY when the FACTS state a non-zero count of currently-open violations" in (
        SUMMARY_SYSTEM_PROMPT
    )
    assert "since complied" in SUMMARY_SYSTEM_PROMPT
    assert "a prior owner's delinquency, likely discharged at the sheriff sale" in (
        SUMMARY_SYSTEM_PROMPT
    )


def test_summary_prompt_forbids_reading_a_named_signal_as_absence() -> None:
    assert "ADDS to the score" in SUMMARY_SYSTEM_PROMPT
    assert "Never describe a named signal as evidence of low distress" in SUMMARY_SYSTEM_PROMPT


def test_summary_prompt_forbids_prescribing_professional_action() -> None:
    assert "never prescribe an action" in SUMMARY_SYSTEM_PROMPT
    assert "not a title search to order" in SUMMARY_SYSTEM_PROMPT
    assert "engaging any professional" in SUMMARY_SYSTEM_PROMPT


def test_summary_prompt_still_reports_a_source_carried_caveat() -> None:
    assert "report it as the source states it" in SUMMARY_SYSTEM_PROMPT
