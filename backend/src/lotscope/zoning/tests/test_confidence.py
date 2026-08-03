import pytest

from lotscope.zoning.confidence import (
    CRITICAL_UNKNOWN_REASONS,
    CriticalUnknown,
    critical_unknown_reasons,
    dimensional_confidence,
    resolve_confidence,
)


def test_dimensional_confidence_tiers() -> None:
    assert dimensional_confidence(lot_area_known=True, lot_width_known=True) == "high"
    assert dimensional_confidence(lot_area_known=True, lot_width_known=False) == "medium"
    assert dimensional_confidence(lot_area_known=False, lot_width_known=True) == "medium"
    assert dimensional_confidence(lot_area_known=False, lot_width_known=False) == "low"


def test_high_survives_only_with_no_critical_unknowns() -> None:
    assert resolve_confidence("high", ()) == "high"


@pytest.mark.parametrize("unknown", sorted(CRITICAL_UNKNOWN_REASONS))
def test_any_single_critical_unknown_blocks_high(unknown: CriticalUnknown) -> None:
    assert resolve_confidence("high", (unknown,)) != "high"


def test_provisional_standards_force_low() -> None:
    assert resolve_confidence("high", ("standards_provisional",)) == "low"
    assert resolve_confidence("medium", ("standards_provisional",)) == "low"


def test_unknowns_do_not_promote_or_further_demote_below_high() -> None:
    assert resolve_confidence("medium", ("height_standard_missing",)) == "medium"
    assert resolve_confidence("low", ("height_standard_missing",)) == "low"
    assert resolve_confidence("low", ()) == "low"


def test_every_critical_unknown_carries_a_user_facing_reason() -> None:
    reasons = critical_unknown_reasons(tuple(CRITICAL_UNKNOWN_REASONS))
    assert len(reasons) == len(CRITICAL_UNKNOWN_REASONS)
    assert all(reason.endswith(".") for reason in reasons)


def test_reasons_are_ordered_and_deduplicated() -> None:
    reasons = critical_unknown_reasons(
        ("height_standard_missing", "dimensions_incomplete", "height_standard_missing")
    )
    assert reasons == [
        CRITICAL_UNKNOWN_REASONS["dimensions_incomplete"],
        CRITICAL_UNKNOWN_REASONS["height_standard_missing"],
    ]
