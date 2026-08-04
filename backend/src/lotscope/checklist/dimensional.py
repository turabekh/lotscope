from dataclasses import dataclass, field
from typing import Any

from lotscope.checklist.schemas import ChecklistItem, ChecklistStatus
from lotscope.zoning.dispositions import disposition_of
from lotscope.zoning.parking import (
    CHAPTER_14_800_SOURCE,
    governing_section,
    parking_requirement,
    required_spaces,
    requirement_phrase,
)

_ZONING = "Zoning & buildability"
_SITE = "Site & servicing"
_TITLE = "Ownership & title"


@dataclass(frozen=True)
class DimensionalContext:
    district_code: str | None = None
    citation_label: str | None = None
    lot_area_sqft: float | None = None
    frontage_ft: float | None = None
    min_lot_area_sqft: float | None = None
    min_lot_width_ft: float | None = None
    max_height_ft: float | None = None
    max_units: int | None = None
    lot_area_per_unit_sqft: float | None = None
    max_floor_area_ratio_pct: float | None = None
    max_occupancy_pct: float | None = None
    front_setback_ft: float | None = None
    rear_setback_ft: float | None = None
    side_setback_ft: float | None = None
    requires_master_plan: bool = False
    permitted_uses: tuple[str, ...] = ()
    by_right_units: int | None = None
    deed_restriction_count: int | None = None
    subdivision_potential: bool | None = None
    standard_loaded: bool = False
    field_dispositions: dict[str, Any] = field(default_factory=dict)


_NO_DISTRICT = "The base district could not be resolved, so this check was not evaluated."


def _unevaluated(code: str, label: str, category: str, detail: str) -> ChecklistItem:
    return ChecklistItem(
        code=code, label=label, category=category, status="not_evaluated", detail=detail
    )


def _standard_missing(
    code: str,
    label: str,
    category: str,
    context: DimensionalContext,
    field_description: str,
    field_name: str = "",
) -> ChecklistItem:
    if context.district_code is None:
        return _unevaluated(code, label, category, _NO_DISTRICT)
    if not context.standard_loaded:
        return _unevaluated(
            code,
            label,
            category,
            f"No zoning standard is loaded for {context.district_code}, "
            "so this check was not evaluated.",
        )
    disposition, note = disposition_of(context.field_dispositions, field_name)
    if disposition == "unregulated":
        qualifier = f" — {note}" if note else ""
        return ChecklistItem(
            code=code,
            label=label,
            category=category,
            status="not_applicable",
            detail=f"{context.district_code} sets {field_description}{qualifier}.",
            source=_cite(context),
        )
    if disposition == "conditional" and note:
        return ChecklistItem(
            code=code,
            label=label,
            category=category,
            status="not_evaluated",
            detail=(
                f"In {context.district_code} this standard is {note}, so it cannot be "
                "reduced to a single figure and is not modelled."
            ),
            source=_cite(context),
        )
    return _unevaluated(
        code,
        label,
        category,
        f"The {context.district_code} standard on file records {field_description}, "
        "so this check was not evaluated.",
    )


def _cite(context: DimensionalContext) -> str | None:
    return context.citation_label or None


def lot_area_item(context: DimensionalContext) -> ChecklistItem:
    minimum = context.min_lot_area_sqft
    actual = context.lot_area_sqft
    if minimum is None:
        return _standard_missing(
            "min_lot_area",
            "Minimum lot area",
            _ZONING,
            context,
            "no minimum lot area",
            "min_lot_area_sqft",
        )
    if actual is None or actual <= 0:
        return _unevaluated(
            "min_lot_area",
            "Minimum lot area",
            _ZONING,
            "Lot area is not recorded, so it cannot be compared.",
        )
    status: ChecklistStatus = "pass" if actual >= minimum else "fail"
    verb = "meets" if status == "pass" else "is below"
    return ChecklistItem(
        code="min_lot_area",
        label="Minimum lot area",
        category=_ZONING,
        status=status,
        detail=(
            f"{actual:,.0f} sqft {verb} the {minimum:,.0f} sqft minimum for "
            f"{context.district_code}."
        ),
        source=_cite(context),
    )


def lot_width_item(context: DimensionalContext) -> ChecklistItem:
    minimum = context.min_lot_width_ft
    actual = context.frontage_ft
    if minimum is None:
        return _standard_missing(
            "min_lot_width",
            "Minimum lot width",
            _ZONING,
            context,
            "no minimum lot width",
            "min_lot_width_ft",
        )
    if actual is None or actual <= 0:
        return _unevaluated(
            "min_lot_width",
            "Minimum lot width",
            _ZONING,
            "Frontage is not recorded for this parcel, so lot width cannot be compared.",
        )
    status: ChecklistStatus = "pass" if actual >= minimum else "fail"
    verb = "meets" if status == "pass" else "is below"
    return ChecklistItem(
        code="min_lot_width",
        label="Minimum lot width",
        category=_ZONING,
        status=status,
        detail=f"{actual:,.0f} ft frontage {verb} the {minimum:,.0f} ft minimum.",
        source=_cite(context),
    )


def height_item(context: DimensionalContext) -> ChecklistItem:
    if context.max_height_ft is None:
        return _standard_missing(
            "max_height",
            "Maximum height",
            _ZONING,
            context,
            "no maximum height",
            "max_height_ft",
        )
    return ChecklistItem(
        code="max_height",
        label="Maximum height",
        category=_ZONING,
        status="pass",
        detail=(
            f"The district caps height at {context.max_height_ft:,.0f} ft; the modelled "
            "envelope is held to that limit."
        ),
        source=_cite(context),
    )


def floor_area_item(context: DimensionalContext) -> ChecklistItem:
    far = context.max_floor_area_ratio_pct
    occupancy = context.max_occupancy_pct
    if far is None and occupancy is None:
        return _standard_missing(
            "floor_area",
            "Floor area & coverage",
            _ZONING,
            context,
            "neither a floor-area ratio nor a lot-coverage limit",
        )
    parts = []
    if occupancy is not None:
        parts.append(f"lot coverage is capped at {occupancy:,.0f}%")
    if far is not None:
        parts.append(f"floor-area ratio at {far:,.0f}%")
    return ChecklistItem(
        code="floor_area",
        label="Floor area & coverage",
        category=_ZONING,
        status="pass",
        detail=f"For {context.district_code}, {' and '.join(parts)}.",
        source=_cite(context),
    )


def yards_item(context: DimensionalContext) -> ChecklistItem:
    setbacks = {
        "front": context.front_setback_ft,
        "side": context.side_setback_ft,
        "rear": context.rear_setback_ft,
    }
    known = {name: value for name, value in setbacks.items() if value is not None}
    if not known:
        return _standard_missing(
            "yards", "Required yards", _ZONING, context, "no yard or setback requirement"
        )
    described = ", ".join(f"{name} {value:,.0f} ft" for name, value in known.items())
    missing = [name for name, value in setbacks.items() if value is None]
    if missing:
        return ChecklistItem(
            code="yards",
            label="Required yards",
            category=_ZONING,
            status="potential_issue",
            detail=(
                f"Required yards: {described}. No {', '.join(missing)} yard is recorded in the "
                "loaded standard, so the buildable envelope may be smaller than modelled."
            ),
            source=_cite(context),
        )
    return ChecklistItem(
        code="yards",
        label="Required yards",
        category=_ZONING,
        status="pass",
        detail=f"Required yards applied to the envelope: {described}.",
        source=_cite(context),
    )


def unit_density_item(context: DimensionalContext) -> ChecklistItem:
    per_unit = context.lot_area_per_unit_sqft
    max_units = context.max_units
    if per_unit is None and max_units is None:
        return _standard_missing(
            "unit_density",
            "Unit density",
            _ZONING,
            context,
            "no density limit",
            "max_units",
        )
    if per_unit is not None and context.lot_area_sqft:
        supported = int(context.lot_area_sqft // per_unit)
        if supported < 1:
            return ChecklistItem(
                code="unit_density",
                label="Unit density",
                category=_ZONING,
                status="fail",
                detail=(
                    f"The district requires {per_unit:,.0f} sqft per unit; "
                    f"{context.lot_area_sqft:,.0f} sqft does not support a single unit by right."
                ),
                source=_cite(context),
            )
        return ChecklistItem(
            code="unit_density",
            label="Unit density",
            category=_ZONING,
            status="pass",
            detail=(
                f"At {per_unit:,.0f} sqft per unit, the lot supports {supported} unit(s) "
                "before other limits are applied."
            ),
            source=_cite(context),
        )
    return ChecklistItem(
        code="unit_density",
        label="Unit density",
        category=_ZONING,
        status="pass",
        detail=f"The district caps density at {max_units} unit(s).",
        source=_cite(context),
    )


def master_plan_item(context: DimensionalContext) -> ChecklistItem:
    if context.district_code is None:
        return _unevaluated("master_plan", "Master plan", _ZONING, _NO_DISTRICT)
    if context.requires_master_plan:
        return ChecklistItem(
            code="master_plan",
            label="Master plan",
            category=_ZONING,
            status="fail",
            detail=(
                "This district requires an approved master plan, which is an entitlement "
                "process before any by-right path."
            ),
            source=_cite(context),
        )
    return ChecklistItem(
        code="master_plan",
        label="Master plan",
        category=_ZONING,
        status="pass",
        detail="No master plan is required for this district.",
        source=_cite(context),
    )


def permitted_use_item(context: DimensionalContext) -> ChecklistItem:
    if not context.permitted_uses:
        return _unevaluated(
            "permitted_use",
            "Permitted uses",
            _ZONING,
            "The loaded standard lists no permitted uses, so use permission was not evaluated.",
        )
    return ChecklistItem(
        code="permitted_use",
        label="Permitted uses",
        category=_ZONING,
        status="pass",
        detail=(
            f"{context.district_code} permits: {', '.join(context.permitted_uses[:6])}. "
            "Residential infill is modelled against these."
        ),
        source=_cite(context),
    )


_LOADING_NOTE = "Loading requirements are separate and are not modelled."

_DWELLING_USE_LABELS = {
    "single_family": "a single-family home",
    "two_family": "a two-family home",
    "multi_family": "multi-family dwellings",
}


def _modelled_dwelling_use(permitted_uses: tuple[str, ...]) -> str | None:
    for use in ("multi_family", "two_family", "single_family"):
        if use in permitted_uses:
            return use
    return None


def parking_item(context: DimensionalContext) -> ChecklistItem:
    district = context.district_code
    if district is None:
        return _unevaluated("parking", "Parking & loading", _SITE, _NO_DISTRICT)

    section = governing_section(district)
    if section is not None:
        return _unevaluated(
            "parking",
            "Parking & loading",
            _SITE,
            f"Parking in {district} is set by {section} rather than the district parking "
            f"tables, so it is not modelled. {_LOADING_NOTE}",
        )

    use = _modelled_dwelling_use(context.permitted_uses)
    requirement = parking_requirement(district, use) if use is not None else None
    if use is None or requirement is None:
        return _unevaluated(
            "parking",
            "Parking & loading",
            _SITE,
            "Parking and loading requirements are not modelled for this district. Confirm the "
            "minimum against Chapter 14-800 before relying on the unit count.",
        )

    phrase = requirement_phrase(requirement)
    subject = _DWELLING_USE_LABELS[use]
    if requirement.spaces == 0:
        detail = (
            f"{district} requires {phrase} for {subject} ({requirement.table}). {_LOADING_NOTE}"
        )
    else:
        spaces = (
            required_spaces(requirement, context.by_right_units) if context.by_right_units else None
        )
        modelled = (
            f" The modelled {context.by_right_units} unit(s) would need {spaces} space(s)."
            if spaces is not None
            else ""
        )
        detail = (
            f"{district} requires {phrase} for {subject} ({requirement.table}).{modelled} "
            f"{_LOADING_NOTE}"
        )
    return ChecklistItem(
        code="parking",
        label="Parking & loading",
        category=_SITE,
        status="pass",
        detail=detail,
        source=CHAPTER_14_800_SOURCE,
    )


def utilities_item(context: DimensionalContext) -> ChecklistItem:
    return _unevaluated(
        "utilities",
        "Utility service",
        _SITE,
        "No utility-connection data is ingested, so water, sewer, and electric service cannot "
        "be confirmed. This is not confirmation that service exists.",
    )


def deed_restriction_item(context: DimensionalContext) -> ChecklistItem:
    count = context.deed_restriction_count
    if count is None:
        return _unevaluated(
            "deed_restrictions",
            "Deed restrictions",
            _TITLE,
            "Recorded deeds were not read for this parcel, so restrictions and easements are "
            "unconfirmed.",
        )
    if count > 0:
        return ChecklistItem(
            code="deed_restrictions",
            label="Deed restrictions",
            category=_TITLE,
            status="potential_issue",
            detail=(
                f"{count} possible restriction or easement found in recorded deed text; "
                "have counsel confirm before relying on the buildable envelope."
            ),
            source="deed_document",
        )
    return ChecklistItem(
        code="deed_restrictions",
        label="Deed restrictions",
        category=_TITLE,
        status="not_evaluated",
        detail=(
            "No restriction language was detected in the deed text held for this parcel. "
            "Deed coverage is partial, so this is not a clear-title confirmation."
        ),
        source="deed_document",
    )


def subdivision_item(context: DimensionalContext) -> ChecklistItem:
    potential = context.subdivision_potential
    if potential is None:
        return _unevaluated(
            "subdivision",
            "Subdivision potential",
            _ZONING,
            "Subdivision potential was not evaluated for this parcel.",
        )
    if potential:
        return ChecklistItem(
            code="subdivision",
            label="Subdivision potential",
            category=_ZONING,
            status="potential_issue",
            detail=(
                "The lot appears large enough to subdivide, which changes the unit count and "
                "requires its own approval."
            ),
            source="subdivision",
        )
    return ChecklistItem(
        code="subdivision",
        label="Subdivision potential",
        category=_ZONING,
        status="not_applicable",
        detail="The lot is not large enough to subdivide under the district minimums.",
        source="subdivision",
    )


DIMENSIONAL_BUILDERS = (
    permitted_use_item,
    lot_area_item,
    lot_width_item,
    height_item,
    floor_area_item,
    yards_item,
    unit_density_item,
    master_plan_item,
    parking_item,
    utilities_item,
    deed_restriction_item,
    subdivision_item,
)


def build_dimensional_items(context: DimensionalContext) -> list[ChecklistItem]:
    return [builder(context) for builder in DIMENSIONAL_BUILDERS]
