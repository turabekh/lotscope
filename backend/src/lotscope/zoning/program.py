from dataclasses import dataclass, field

from lotscope.core.provenance import FieldState
from lotscope.zoning.buildability import FootprintBasis, UnitBasis
from lotscope.zoning.confidence import Confidence
from lotscope.zoning.posture import BuildabilityPosture, resolve_posture, unit_claim


@dataclass(frozen=True)
class ProgramInputs:
    district_code: str | None = None
    cited_section: str | None = None
    lot_area_sqft: float | None = None
    permitted_uses: tuple[str, ...] = ()
    requires_master_plan: bool = False
    can_build_by_right: bool = False
    needs_variance: bool | None = None
    by_right_units: int | None = None
    unit_basis: UnitBasis | None = None
    max_height_ft: float | None = None
    height_unregulated: bool = False
    max_floor_area_ratio_pct: float | None = None
    max_occupancy_pct: float | None = None
    buildable_area_sqft: float | None = None
    footprint_basis: FootprintBasis = "unavailable"
    confidence: Confidence = "low"
    outstanding_checks: tuple[str, ...] = ()
    flagged_checks: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProgramClaim:
    label: str
    value: str
    state: FieldState


@dataclass(frozen=True)
class DevelopmentProgram:
    statement: str
    claims: tuple[ProgramClaim, ...] = ()
    citation: str | None = None
    conditions: tuple[str, ...] = field(default_factory=tuple)


_USE_LABELS = {
    "single_family": "single-family",
    "two_family": "two-family",
    "multi_family": "multi-family",
    "commercial": "commercial",
    "industrial": "industrial",
    "institutional": "institutional",
    "civic": "civic",
    "parks": "park",
    "recreation": "recreation",
    "entertainment": "entertainment",
    "stadium": "stadium",
    "airport": "airport",
}

_UNIT_BASIS_NOTE = {
    "per_unit": "from the district's lot-area-per-unit rule",
    "far_estimate": "estimated from the floor-area ratio, not a stated unit cap",
    "flat_cap": "the district's flat unit cap",
}

_NO_DISTRICT_STATEMENT = (
    "The base zoning district could not be resolved for this parcel, so no development "
    "program can be described."
)


def _join(values: list[str]) -> str:
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    return f"{', '.join(values[:-1])} and {values[-1]}"


def _use_label(use: str) -> str:
    return _USE_LABELS.get(use, use.replace("_", " "))


def _use_phrase(uses: tuple[str, ...]) -> str:
    return _join([_use_label(use) for use in uses])


def _bulk_sentence(inputs: ProgramInputs) -> str | None:
    district = inputs.district_code
    if inputs.max_height_ft is not None:
        return f"{district} caps height at {inputs.max_height_ft:,.0f} ft."
    if not inputs.height_unregulated:
        return (
            f"No by-right height is recorded for {district}, so the vertical envelope "
            "is unverified."
        )
    limits = []
    if inputs.max_floor_area_ratio_pct is not None:
        limits.append(f"a {inputs.max_floor_area_ratio_pct:,.0f}% floor-area ratio")
    if inputs.max_occupancy_pct is not None:
        limits.append(f"a {inputs.max_occupancy_pct:,.0f}% lot-coverage limit")
    if not limits:
        return f"{district} sets no maximum height."
    return f"{district} sets no maximum height; bulk is governed by {_join(limits)} instead."


def _footprint_sentence(inputs: ProgramInputs) -> str | None:
    if inputs.buildable_area_sqft is None:
        return "The buildable footprint could not be estimated for this parcel."
    if inputs.footprint_basis == "setback_calculated":
        return (
            f"After the district's required yards, the buildable footprint calculates to about "
            f"{inputs.buildable_area_sqft:,.0f} sq ft."
        )
    return (
        f"The buildable footprint is estimated at about {inputs.buildable_area_sqft:,.0f} sq ft "
        "from lot coverage rather than measured setbacks, so treat it as indicative."
    )


def _use_sentence(inputs: ProgramInputs) -> str:
    district = inputs.district_code
    area = (
        f"this {inputs.lot_area_sqft:,.0f} sq ft {district} lot"
        if inputs.lot_area_sqft is not None
        else f"this {district} lot"
    )
    if inputs.requires_master_plan:
        return (
            f"On {area}, development is not permitted by right — {district} requires an approved "
            "master plan before any construction."
        )
    if not inputs.permitted_uses:
        return (
            f"On {area}, no by-right uses are recorded for the district, so permitted "
            "development is unverified."
        )
    uses = _use_phrase(inputs.permitted_uses)
    if inputs.needs_variance:
        return (
            f"On {area}, {uses} uses are listed for the district, but the lot does not meet "
            "the dimensional minimums — a variance or special exception is likely required."
        )
    if inputs.can_build_by_right:
        return f"On {area}, {uses} uses are permitted by right."
    return (
        f"On {area}, {uses} uses are listed for the district, but by-right eligibility could "
        "not be confirmed from the recorded dimensions."
    )


def _units_sentence(inputs: ProgramInputs) -> str | None:
    if inputs.by_right_units is None or inputs.requires_master_plan:
        return None
    note = _UNIT_BASIS_NOTE.get(inputs.unit_basis or "", "")
    suffix = f" — {note}" if note else ""
    if inputs.needs_variance:
        return (
            f"Were a variance granted, the district standards would support about "
            f"{inputs.by_right_units:,} dwelling unit(s){suffix}."
        )
    return (
        f"The district standards support about {inputs.by_right_units:,} dwelling unit(s) "
        f"before other limits apply{suffix}."
    )


def program_posture(inputs: ProgramInputs) -> BuildabilityPosture:
    return resolve_posture(
        requires_master_plan=inputs.requires_master_plan,
        can_build_by_right=inputs.can_build_by_right,
        needs_variance=inputs.needs_variance,
    )


def _claims(inputs: ProgramInputs) -> tuple[ProgramClaim, ...]:
    claims: list[ProgramClaim] = []
    if inputs.district_code:
        claims.append(ProgramClaim("Base district", inputs.district_code, "verified"))
    if inputs.lot_area_sqft is not None:
        claims.append(ProgramClaim("Lot area", f"{inputs.lot_area_sqft:,.0f} sq ft", "verified"))
    if inputs.permitted_uses:
        claims.append(
            ProgramClaim("Permitted uses", _use_phrase(inputs.permitted_uses), "verified")
        )
    if inputs.max_height_ft is not None:
        claims.append(
            ProgramClaim("Maximum height", f"{inputs.max_height_ft:,.0f} ft", "calculated")
        )
    elif inputs.height_unregulated:
        claims.append(ProgramClaim("Maximum height", "not regulated by the district", "verified"))
    else:
        claims.append(ProgramClaim("Maximum height", "not recorded", "unavailable"))
    units = unit_claim(program_posture(inputs), inputs.by_right_units, unit_basis=inputs.unit_basis)
    claims.append(ProgramClaim(units.label, units.value, units.state))
    if inputs.buildable_area_sqft is not None:
        footprint_state: FieldState = (
            "calculated" if inputs.footprint_basis == "setback_calculated" else "estimated"
        )
        claims.append(
            ProgramClaim(
                "Buildable footprint",
                f"{inputs.buildable_area_sqft:,.0f} sq ft",
                footprint_state,
            )
        )
    else:
        claims.append(ProgramClaim("Buildable footprint", "not determined", "unavailable"))
    return tuple(claims)


def _conditions(inputs: ProgramInputs) -> tuple[str, ...]:
    conditions: list[str] = []
    if inputs.flagged_checks:
        conditions.append(
            f"Flagged for a closer look: {_join(list(inputs.flagged_checks))}. "
            "The figures above may change once these are resolved."
        )
    if inputs.outstanding_checks:
        conditions.append(
            "This program reads the base district only. Still unevaluated: "
            f"{_join(list(inputs.outstanding_checks))}."
        )
    if inputs.confidence != "high":
        conditions.append(
            f"Confidence in this read is {inputs.confidence} — see the checks below for why."
        )
    conditions.append(
        "Informational only, not a zoning determination. Confirm with the city before relying "
        "on it."
    )
    return tuple(conditions)


def compose_development_program(inputs: ProgramInputs) -> DevelopmentProgram:
    if not inputs.district_code:
        return DevelopmentProgram(
            statement=_NO_DISTRICT_STATEMENT,
            claims=(),
            citation=None,
            conditions=(
                "Informational only, not a zoning determination. Confirm with the city before "
                "relying on it.",
            ),
        )
    sentences = [
        _use_sentence(inputs),
        _units_sentence(inputs),
        _bulk_sentence(inputs),
        _footprint_sentence(inputs),
    ]
    return DevelopmentProgram(
        statement=" ".join(sentence for sentence in sentences if sentence),
        claims=_claims(inputs),
        citation=inputs.cited_section,
        conditions=_conditions(inputs),
    )
