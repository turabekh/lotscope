from dataclasses import dataclass
from typing import Literal

from lotscope.core.provenance import FieldState
from lotscope.zoning.buildability import UnitBasis

BuildabilityPosture = Literal[
    "by_right",
    "variance_required",
    "master_plan_required",
    "undetermined",
]

_POSTURE_LABELS: dict[BuildabilityPosture, str] = {
    "by_right": "Dimensionally eligible",
    "variance_required": "Variance likely",
    "master_plan_required": "Master plan required",
    "undetermined": "Buildability uncertain",
}

_UNIT_LABELS: dict[BuildabilityPosture, str] = {
    "by_right": "By-right units",
    "variance_required": "Units if a variance is granted",
    "master_plan_required": "By-right units",
    "undetermined": "Units the standards would support",
}

_MASTER_PLAN_UNIT_VALUE = "none — master plan required"
_UNDETERMINED_UNIT_VALUE = "not determined"


@dataclass(frozen=True)
class UnitClaim:
    label: str
    value: str
    state: FieldState


def resolve_posture(
    *,
    requires_master_plan: bool,
    can_build_by_right: bool | None,
    needs_variance: bool | None,
) -> BuildabilityPosture:
    if requires_master_plan:
        return "master_plan_required"
    if can_build_by_right:
        return "by_right"
    if needs_variance:
        return "variance_required"
    return "undetermined"


def posture_label(posture: BuildabilityPosture) -> str:
    return _POSTURE_LABELS[posture]


def unit_claim(
    posture: BuildabilityPosture,
    by_right_units: int | None,
    *,
    unit_basis: UnitBasis | None = None,
) -> UnitClaim:
    label = _UNIT_LABELS[posture]
    if posture == "master_plan_required":
        return UnitClaim(label, _MASTER_PLAN_UNIT_VALUE, "unavailable")
    if by_right_units is None:
        return UnitClaim(label, _UNDETERMINED_UNIT_VALUE, "unavailable")
    state: FieldState = "estimated" if unit_basis == "far_estimate" else "calculated"
    return UnitClaim(label, f"{by_right_units:,}", state)
