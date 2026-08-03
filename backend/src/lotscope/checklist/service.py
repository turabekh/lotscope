from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.checklist.dimensional import DimensionalContext
from lotscope.checklist.logic import build_checklist
from lotscope.checklist.schemas import (
    ChecklistItem,
    DevelopmentProgramOut,
    ParcelChecklist,
    ProgramClaimOut,
)
from lotscope.core.config import get_settings
from lotscope.documents.service import get_deed_restrictions
from lotscope.parcels.abatement import has_active_exemption
from lotscope.parcels.schemas import ParcelDetail
from lotscope.parcels.service import get_parcel_detail
from lotscope.subdivision.service import analyze_parcel_subdivision
from lotscope.verdict.service import get_or_compute_current_verdict
from lotscope.zoning.buildability import FootprintBasis, UnitBasis
from lotscope.zoning.confidence import critical_unknown_reasons
from lotscope.zoning.dispositions import is_unregulated
from lotscope.zoning.program import ProgramInputs, compose_development_program
from lotscope.zoning.schemas import BuildabilityResult
from lotscope.zoning.service import assess_parcel, get_parcel_standard

_TAX_KNOWN_SQL = text("SELECT is_delinquent FROM tax_status WHERE parcel_number = :parcel_number")


async def _tax_status_unknown(session: AsyncSession, parcel_number: str) -> bool:
    row = (await session.execute(_TAX_KNOWN_SQL, {"parcel_number": parcel_number})).one_or_none()
    return row is not None and row.is_delinquent is None


async def _dimensional_context(
    session: AsyncSession,
    parcel_number: str,
    detail: ParcelDetail | None,
    resolved_district_code: str | None,
) -> DimensionalContext:
    standard = await get_parcel_standard(session, parcel_number)
    try:
        deeds = await get_deed_restrictions(
            session,
            parcel_number,
            record_url_template=get_settings().philadox_document_url_template,
        )
        deed_count: int | None = deeds.count
    except Exception:
        deed_count = None
    subdivision = await analyze_parcel_subdivision(session, parcel_number)
    return DimensionalContext(
        district_code=standard.code if standard is not None else resolved_district_code,
        standard_loaded=standard is not None,
        field_dispositions=standard.field_dispositions if standard is not None else {},
        citation_label=standard.citation_label if standard is not None else None,
        lot_area_sqft=detail.lot_area_sqft if detail is not None else None,
        frontage_ft=detail.frontage_ft if detail is not None else None,
        min_lot_area_sqft=standard.min_lot_area_sqft if standard is not None else None,
        min_lot_width_ft=standard.min_lot_width_ft if standard is not None else None,
        max_height_ft=standard.max_height_ft if standard is not None else None,
        max_units=standard.max_units if standard is not None else None,
        lot_area_per_unit_sqft=(standard.lot_area_per_unit_sqft if standard is not None else None),
        max_floor_area_ratio_pct=(
            standard.max_floor_area_ratio_pct if standard is not None else None
        ),
        max_occupancy_pct=standard.max_occupancy_pct if standard is not None else None,
        front_setback_ft=standard.front_setback_ft if standard is not None else None,
        rear_setback_ft=standard.rear_setback_ft if standard is not None else None,
        side_setback_ft=standard.side_setback_ft if standard is not None else None,
        requires_master_plan=standard.requires_master_plan if standard is not None else False,
        permitted_uses=tuple(standard.permitted_uses) if standard is not None else (),
        deed_restriction_count=deed_count,
        subdivision_potential=(subdivision.can_subdivide if subdivision is not None else None),
    )


def _unit_basis(dimensional: DimensionalContext) -> UnitBasis | None:
    if dimensional.lot_area_per_unit_sqft is not None:
        return "per_unit"
    if dimensional.max_units is not None:
        return "flat_cap"
    return None


def _footprint_basis(buildability: BuildabilityResult) -> FootprintBasis:
    if buildability.buildable_area_sqft is None:
        return "unavailable"
    if "footprint_not_setback_derived" in buildability.critical_unknowns:
        return "coverage_estimate"
    return "setback_calculated"


def _program_for(
    buildability: BuildabilityResult | None,
    dimensional: DimensionalContext,
    items: list[ChecklistItem],
) -> DevelopmentProgramOut | None:
    if buildability is None:
        return None
    program = compose_development_program(
        ProgramInputs(
            district_code=buildability.district_code,
            cited_section=buildability.cited_section,
            lot_area_sqft=dimensional.lot_area_sqft,
            permitted_uses=dimensional.permitted_uses,
            requires_master_plan=dimensional.requires_master_plan,
            can_build_by_right=buildability.can_build_by_right,
            needs_variance=buildability.needs_variance,
            by_right_units=buildability.by_right_units,
            unit_basis=_unit_basis(dimensional),
            max_height_ft=buildability.max_height_ft,
            height_unregulated=is_unregulated(dimensional.field_dispositions, "max_height_ft"),
            max_floor_area_ratio_pct=dimensional.max_floor_area_ratio_pct,
            max_occupancy_pct=dimensional.max_occupancy_pct,
            buildable_area_sqft=buildability.buildable_area_sqft,
            footprint_basis=_footprint_basis(buildability),
            confidence=buildability.confidence,
            outstanding_checks=tuple(
                item.label for item in items if item.status == "not_evaluated"
            ),
            flagged_checks=tuple(
                item.label for item in items if item.status in {"potential_issue", "fail"}
            ),
        )
    )
    return DevelopmentProgramOut(
        statement=program.statement,
        claims=[
            ProgramClaimOut(label=claim.label, value=claim.value, state=claim.state)
            for claim in program.claims
        ],
        citation=program.citation,
        conditions=list(program.conditions),
    )


async def build_parcel_checklist(
    session: AsyncSession, parcel_number: str
) -> ParcelChecklist | None:
    verdict = await get_or_compute_current_verdict(session, parcel_number)
    if verdict is None:
        return None
    await session.commit()
    detail = await get_parcel_detail(session, parcel_number)
    has_abatement = (
        has_active_exemption(detail.exempt_land, detail.exempt_building)
        if detail is not None
        else None
    )
    market = parcel_number.split(":", 1)[0]
    buildability = await assess_parcel(session, parcel_number)
    dimensional = await _dimensional_context(
        session,
        parcel_number,
        detail,
        buildability.district_code if buildability is not None else None,
    )
    items, summary = build_checklist(
        verdict,
        has_abatement=has_abatement,
        market_code=market,
        tax_status_unknown=await _tax_status_unknown(session, parcel_number),
        dimensional=dimensional,
    )
    return ParcelChecklist(
        parcel_number=parcel_number,
        items=items,
        summary=summary,
        program=_program_for(buildability, dimensional, items),
        buildability_confidence=buildability.confidence if buildability is not None else None,
        buildability_confidence_reasons=(
            critical_unknown_reasons(buildability.critical_unknowns)
            if buildability is not None
            else []
        ),
        computed_at=datetime.now(UTC),
    )
