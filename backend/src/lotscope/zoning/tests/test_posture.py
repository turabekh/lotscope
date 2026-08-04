import pytest

from lotscope.zoning.posture import (
    BuildabilityPosture,
    posture_label,
    resolve_posture,
    unit_claim,
)


def test_master_plan_outranks_every_other_signal() -> None:
    assert (
        resolve_posture(
            requires_master_plan=True,
            can_build_by_right=True,
            needs_variance=False,
        )
        == "master_plan_required"
    )


def test_by_right_requires_the_explicit_flag() -> None:
    assert (
        resolve_posture(
            requires_master_plan=False,
            can_build_by_right=True,
            needs_variance=False,
        )
        == "by_right"
    )


def test_variance_when_not_by_right() -> None:
    assert (
        resolve_posture(
            requires_master_plan=False,
            can_build_by_right=False,
            needs_variance=True,
        )
        == "variance_required"
    )


def test_undetermined_when_conformance_is_unresolved() -> None:
    assert (
        resolve_posture(
            requires_master_plan=False,
            can_build_by_right=None,
            needs_variance=None,
        )
        == "undetermined"
    )


def test_a_master_plan_lot_never_reports_a_unit_count() -> None:
    claim = unit_claim("master_plan_required", 4)
    assert claim.value == "none — master plan required"
    assert claim.state == "unavailable"
    assert "4" not in claim.value


def test_units_under_a_variance_are_not_labelled_by_right() -> None:
    claim = unit_claim("variance_required", 2)
    assert claim.label == "Units if a variance is granted"
    assert claim.value == "2"
    assert "By-right" not in claim.label


def test_by_right_units_keep_the_plain_label() -> None:
    claim = unit_claim("by_right", 2)
    assert claim.label == "By-right units"
    assert claim.value == "2"


def test_unresolved_conformance_does_not_promise_by_right_units() -> None:
    claim = unit_claim("undetermined", 3)
    assert claim.label == "Units the standards would support"
    assert "By-right" not in claim.label


def test_far_derived_counts_are_estimated_not_calculated() -> None:
    assert unit_claim("by_right", 2, unit_basis="far_estimate").state == "estimated"
    assert unit_claim("by_right", 2, unit_basis="per_unit").state == "calculated"


def test_absent_count_is_unavailable_under_every_posture() -> None:
    for posture in ("by_right", "variance_required", "undetermined"):
        claim = unit_claim(posture, None)
        assert claim.value == "not determined"
        assert claim.state == "unavailable"


@pytest.mark.parametrize(
    ("posture", "expected"),
    [
        ("by_right", "Dimensionally eligible"),
        ("variance_required", "Variance likely"),
        ("master_plan_required", "Master plan required"),
        ("undetermined", "Buildability uncertain"),
    ],
)
def test_every_posture_has_a_headline_label(posture: BuildabilityPosture, expected: str) -> None:
    assert posture_label(posture) == expected
