from collections.abc import Sequence
from typing import Literal

Confidence = Literal["high", "medium", "low"]

CriticalUnknown = Literal[
    "dimensions_incomplete",
    "district_uncorroborated",
    "conformance_unresolved",
    "footprint_not_setback_derived",
    "height_standard_missing",
    "permitted_uses_missing",
    "standards_provisional",
]

CRITICAL_UNKNOWN_REASONS: dict[CriticalUnknown, str] = {
    "dimensions_incomplete": (
        "Lot area or width is missing from the parcel record, so the by-right read "
        "could not be fully verified."
    ),
    "district_uncorroborated": (
        "The zoning district comes from a single source that no second source confirms; "
        "verify the district before relying on it."
    ),
    "conformance_unresolved": (
        "Conformance with the district minimums could not be determined from the "
        "recorded lot dimensions."
    ),
    "footprint_not_setback_derived": (
        "The buildable footprint is a lot-coverage estimate rather than a setback "
        "calculation, because setback standards or lot depth are missing."
    ),
    "height_standard_missing": (
        "No by-right height standard is recorded for this district, so the vertical "
        "envelope is unverified."
    ),
    "permitted_uses_missing": (
        "No by-right uses are recorded for this district, so permitted development is unverified."
    ),
    "standards_provisional": (
        "Zoning standards for this market are provisional pending local review."
    ),
}

_UNKNOWNS_FORCING_LOW: frozenset[str] = frozenset({"standards_provisional"})


def dimensional_confidence(*, lot_area_known: bool, lot_width_known: bool) -> Confidence:
    known = (lot_area_known, lot_width_known)
    if all(known):
        return "high"
    if any(known):
        return "medium"
    return "low"


def resolve_confidence(base: Confidence, unknowns: Sequence[CriticalUnknown]) -> Confidence:
    if _UNKNOWNS_FORCING_LOW.intersection(unknowns):
        return "low"
    if base == "high" and unknowns:
        return "medium"
    return base


def critical_unknown_reasons(unknowns: Sequence[CriticalUnknown]) -> list[str]:
    ordered = [unknown for unknown in CRITICAL_UNKNOWN_REASONS if unknown in set(unknowns)]
    return [CRITICAL_UNKNOWN_REASONS[unknown] for unknown in ordered]
