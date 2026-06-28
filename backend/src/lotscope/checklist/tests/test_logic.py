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
    assert statuses["ownership"] == "pass"
    assert statuses["valuation"] == "pass"
    assert statuses["deal"] == "pass"
    assert summary.ready is True
    assert summary.failures == 0


def test_every_category_always_present() -> None:
    items, _ = build_checklist(_verdict())
    codes = {item.code for item in items}
    assert codes == {"zoning", "liens_taxes", "li", "flood", "ownership", "valuation", "deal"}


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
    assert _item(items, "flood").status == "warn"


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


def test_variance_zoning_warns() -> None:
    items, _ = build_checklist(
        _verdict(can_build_by_right=False, needs_variance=True, by_right_units=None)
    )
    assert _item(items, "zoning").status == "warn"


def test_thin_comps_valuation_warns() -> None:
    items, _ = build_checklist(_verdict(value_confidence=0.3))
    assert _item(items, "valuation").status == "warn"


def test_missing_value_warns() -> None:
    items, _ = build_checklist(_verdict(value_estimate_low=None, value_estimate_high=None))
    assert _item(items, "valuation").status == "warn"


def test_unprofitable_deal_warns() -> None:
    items, _ = build_checklist(
        _verdict(is_underpriced=False, est_margin=-0.5, max_allowable_offer=10000.0)
    )
    assert _item(items, "deal").status == "warn"


def test_unmodelable_deal_is_info() -> None:
    items, _ = build_checklist(_verdict(max_allowable_offer=None))
    assert _item(items, "deal").status == "info"
