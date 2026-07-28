from datetime import UTC, datetime
from typing import Any

from lotscope.checklist.logic import build_checklist
from lotscope.verdict.schemas import VerdictResult

_NOW = datetime(2026, 6, 28, tzinfo=UTC)


def _verdict(**overrides: Any) -> VerdictResult:
    base: dict[str, Any] = {
        "parcel_number": "1",
        "verdict_version": "v2",
        "buildability_score": 80.0,
        "opportunity_score": 75.0,
        "summary": "",
        "can_build_by_right": True,
        "by_right_units": 2,
        "max_height_ft": 38.0,
        "needs_variance": False,
        "buildable_area_sqft": 1400.0,
        "value_estimate_low": 180000.0,
        "value_estimate_high": 220000.0,
        "value_confidence": 0.9,
        "assessment_market_gap": 0.0,
        "arv": 600000.0,
        "est_profit": 90000.0,
        "est_margin": 0.15,
        "max_allowable_offer": 150000.0,
        "deal_score": 60.0,
        "is_underpriced": True,
        "risk_score": 10.0,
        "risk_flags": [],
        "sources": [],
        "computed_at": _NOW,
    }
    base.update(overrides)
    return VerdictResult(**base)


def _item(items: list[Any], code: str) -> Any:
    return next(item for item in items if item.code == code)


def test_clean_parcel_is_all_pass() -> None:
    items, summary = build_checklist(_verdict())
    statuses = {item.code: item.status for item in items}
    assert statuses["zoning"] == "pass"
    assert statuses["liens_taxes"] == "pass"
    assert statuses["li"] == "pass"
    assert statuses["flood"] == "pass"
    assert statuses["access"] == "pass"
    assert statuses["ownership"] == "pass"
    assert statuses["overlays"] == "pass"
    assert statuses["valuation"] == "pass"
    assert statuses["deal"] == "pass"
    assert summary.ready is True
    assert summary.failures == 0


def test_abatement_item_absent_by_default() -> None:
    items, _ = build_checklist(_verdict())
    assert not any(item.code == "abatement" for item in items)


def test_abatement_item_present_when_flagged() -> None:
    items, summary = build_checklist(_verdict(), has_abatement=True)
    abatement = _item(items, "abatement")
    assert abatement.category == "Liens & taxes"
    assert abatement.status == "not_evaluated"
    assert summary.ready is True


def test_every_category_always_present() -> None:
    items, _ = build_checklist(_verdict())
    codes = {item.code for item in items}
    assert codes == {
        "zoning",
        "liens_taxes",
        "li",
        "flood",
        "access",
        "ownership",
        "overlays",
        "valuation",
        "deal",
    }


def test_high_severity_flag_fails_its_category() -> None:
    flags = [
        {
            "code": "tax_delinquency",
            "severity": "high",
            "label": "Tax delinquency",
            "detail": "$45,000 owed over 6 years.",
            "source": "tax_status",
        }
    ]
    items, summary = build_checklist(_verdict(risk_flags=flags))
    liens = _item(items, "liens_taxes")
    assert liens.status == "fail"
    assert "45,000" in liens.detail
    assert liens.source == "tax_status"
    assert summary.ready is False
    assert summary.failures == 1


def test_medium_flag_warns() -> None:
    flags = [
        {
            "code": "flood_zone",
            "severity": "medium",
            "label": "FEMA flood zone",
            "detail": "Intersects flood zone AE.",
            "source": "flood_zone",
        }
    ]
    items, _ = build_checklist(_verdict(risk_flags=flags))
    assert _item(items, "flood").status == "potential_issue"


def test_worst_severity_wins_within_a_category() -> None:
    flags = [
        {"code": "li_violations", "severity": "low", "label": "L&I", "detail": "2 violations."},
        {
            "code": "unsafe_structure",
            "severity": "high",
            "label": "Unsafe",
            "detail": "Unsafe structure.",
        },
    ]
    items, _ = build_checklist(_verdict(risk_flags=flags))
    assert _item(items, "li").status == "fail"


def test_estate_owner_warns_ownership_category() -> None:
    flags = [
        {
            "code": "estate_owner",
            "severity": "medium",
            "label": "Estate / deceased owner",
            "detail": "Owner of record appears to be an estate or deceased owner.",
            "source": "parcel",
        }
    ]
    items, _ = build_checklist(_verdict(risk_flags=flags))
    ownership = _item(items, "ownership")
    assert ownership.status == "potential_issue"
    assert "estate" in ownership.detail.lower()
    assert ownership.source == "parcel"


def test_multiple_owners_is_info_in_ownership_category() -> None:
    flags = [
        {
            "code": "multiple_owners",
            "severity": "low",
            "label": "Additional owners on record",
            "detail": "Owner of record lists unnamed additional parties.",
            "source": "parcel",
        }
    ]
    items, _ = build_checklist(_verdict(risk_flags=flags))
    assert _item(items, "ownership").status == "potential_issue"


def test_public_and_estate_flags_combine_in_ownership() -> None:
    flags = [
        {"code": "public_ownership", "severity": "medium", "detail": "City owned."},
        {"code": "estate_owner", "severity": "medium", "detail": "Estate owner."},
    ]
    items, _ = build_checklist(_verdict(risk_flags=flags))
    ownership = _item(items, "ownership")
    assert ownership.status == "potential_issue"
    assert "City owned." in ownership.detail
    assert "Estate owner." in ownership.detail


def test_no_street_access_flag_surfaces_in_access_category() -> None:
    flags = [
        {
            "code": "no_street_access",
            "severity": "low",
            "label": "No street frontage detected",
            "detail": "No mapped street within 75 ft of the parcel.",
            "source": "street_centerline",
        }
    ]
    items, _ = build_checklist(_verdict(risk_flags=flags))
    access = _item(items, "access")
    assert access.status == "potential_issue"
    assert access.source == "street_centerline"


def test_historic_district_flag_surfaces_in_overlays_category() -> None:
    flags = [
        {
            "code": "historic_district",
            "severity": "low",
            "label": "Historic district overlay",
            "detail": "Parcel sits in the Society Hill historic district.",
            "source": "historicdistricts_local",
        }
    ]
    items, _ = build_checklist(_verdict(risk_flags=flags))
    overlays = _item(items, "overlays")
    assert overlays.status == "potential_issue"
    assert "Society Hill" in overlays.detail
    assert overlays.source == "historicdistricts_local"


def test_variance_zoning_warns() -> None:
    items, _ = build_checklist(
        _verdict(can_build_by_right=False, needs_variance=True, by_right_units=None)
    )
    assert _item(items, "zoning").status == "potential_issue"


def test_thin_comps_valuation_warns() -> None:
    items, _ = build_checklist(_verdict(value_confidence=0.3))
    assert _item(items, "valuation").status == "potential_issue"


def test_missing_value_warns() -> None:
    items, _ = build_checklist(_verdict(value_estimate_low=None, value_estimate_high=None))
    assert _item(items, "valuation").status == "potential_issue"


def test_unprofitable_deal_warns() -> None:
    items, _ = build_checklist(
        _verdict(is_underpriced=False, est_margin=-0.5, max_allowable_offer=10000.0)
    )
    assert _item(items, "deal").status == "potential_issue"


def test_unmodelable_deal_is_info() -> None:
    items, _ = build_checklist(_verdict(max_allowable_offer=None))
    assert _item(items, "deal").status == "not_evaluated"


def test_overlay_and_rco_flags_surface_in_overlays_category() -> None:
    flags = [
        {
            "code": "overlay_district",
            "severity": "low",
            "label": "Zoning overlay district",
            "detail": "Parcel is in overlay /NCA — check Title 14 §14-500 series.",
            "source": "zoning_overlays",
        },
        {
            "code": "rco",
            "severity": "low",
            "label": "Registered Community Organization",
            "detail": "RCO: Test RCO — community meeting required for variances.",
            "source": "zoning_rco",
        },
    ]
    items, _ = build_checklist(_verdict(risk_flags=flags))
    overlays = _item(items, "overlays")
    assert overlays.status == "potential_issue"
    assert "/NCA" in overlays.detail
    assert "Test RCO" in overlays.detail


def test_an_unevaluated_check_can_never_report_as_a_pass() -> None:
    items, _ = build_checklist(_verdict(risk_flags=[]), market_code="wlm")
    unevaluated = [item for item in items if item.status == "not_evaluated"]
    assert unevaluated, "a market with structural data gaps must show unevaluated checks"
    for item in unevaluated:
        assert item.status != "pass"
        assert item.detail.strip(), f"{item.code} must say why it was not evaluated"


def test_a_market_with_no_source_names_the_check_rather_than_omitting_it() -> None:
    wlm_codes = {item.code for item in build_checklist(_verdict(), market_code="wlm")[0]}
    phl_codes = {item.code for item in build_checklist(_verdict(), market_code="phl")[0]}
    assert wlm_codes == phl_codes


def test_the_summary_counts_unevaluated_checks_separately() -> None:
    _, summary = build_checklist(_verdict(risk_flags=[]), market_code="wlm")
    assert summary.not_evaluated > 0


def test_silence_in_a_covered_market_is_a_pass_not_an_unevaluated_check() -> None:
    items, _ = build_checklist(_verdict(risk_flags=[]), market_code="phl")
    liens = _item(items, "liens_taxes")
    assert liens.status == "pass"


def test_an_unknown_tax_balance_is_not_reported_as_clear() -> None:
    items, _ = build_checklist(_verdict(risk_flags=[]), tax_status_unknown=True)
    liens = _item(items, "liens_taxes")
    assert liens.status == "not_evaluated"
    assert "not a clean-title" in liens.detail
    assert "No tax delinquency" not in liens.detail


def test_a_known_clear_tax_status_still_reports_a_pass() -> None:
    items, _ = build_checklist(_verdict(risk_flags=[]), tax_status_unknown=False)
    assert _item(items, "liens_taxes").status == "pass"


def test_an_actual_delinquency_outranks_the_unknown_state() -> None:
    flags = [
        {
            "code": "tax_delinquency",
            "severity": "high",
            "detail": "$40,000 owed.",
            "source": "tax_status",
        }
    ]
    items, _ = build_checklist(_verdict(risk_flags=flags), tax_status_unknown=True)
    liens = _item(items, "liens_taxes")
    assert liens.status == "fail"
    assert "40,000" in liens.detail


def test_an_unknown_tax_balance_counts_as_unevaluated_not_as_clear() -> None:
    _, summary = build_checklist(_verdict(risk_flags=[]), tax_status_unknown=True)
    _, known = build_checklist(_verdict(risk_flags=[]), tax_status_unknown=False)
    assert summary.not_evaluated > known.not_evaluated
    assert summary.passed < known.passed


def test_unknown_abatement_shows_an_unevaluated_item_not_silence() -> None:
    items, _ = build_checklist(_verdict(), has_abatement=None)
    abatement = next(item for item in items if item.code == "abatement")
    assert abatement.status == "not_evaluated"
    assert "neither confirmed nor ruled out" in abatement.detail


def test_reported_absent_abatement_shows_no_item() -> None:
    items, _ = build_checklist(_verdict(), has_abatement=False)
    assert all(item.code != "abatement" for item in items)
