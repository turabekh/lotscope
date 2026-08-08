from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import get_settings
from lotscope.deal.analysis import DealAssumptions, DealInputs
from lotscope.deal.case_analysis import CaseAnalysis, analyze_cases
from lotscope.deal.inventory import build_assumption_set, mao_disclosure
from lotscope.deal.sensitivity import SensitivityGrid, build_grid
from lotscope.deal.service import _assumptions, market_overrides_for
from lotscope.underwriting.service import default_assumptions
from lotscope.valuation.avm import land_use_class
from lotscope.valuation.service import find_comps
from lotscope.zoning.schemas import BuildabilityResult
from lotscope.zoning.service import compute_envelope


@dataclass(frozen=True)
class UnderwritingAnalysis:
    assumptions: list[dict[str, object]]
    mao: dict[str, object]
    cases: CaseAnalysis
    sensitivity: SensitivityGrid
    profile_version: int | None
    computed_at: datetime


async def build_underwriting(
    session: AsyncSession,
    parcel_number: str,
    *,
    owner_id: int,
    market_code: str,
    base_zoning_code: str | None,
    market_value: float | None,
    buildability: BuildabilityResult | None,
    land_value: float | None,
    acquisition_price: float | None = None,
) -> UnderwritingAnalysis:
    computed_at = datetime.now(UTC)
    settings = get_settings()

    profile_overrides = await default_assumptions(session, owner_id)
    market_overrides = await market_overrides_for(session, market_code)
    assumption_set = build_assumption_set(
        settings=settings,
        market_overrides=market_overrides,
        user_overrides=profile_overrides,
    )

    envelope = await compute_envelope(session, parcel_number)
    finished_comps, _ = await find_comps(
        session,
        parcel_number,
        vacant_only=False,
        use_class=land_use_class(base_zoning_code),
    )

    inputs = DealInputs(
        units=buildability.by_right_units if buildability is not None else None,
        buildable_area_sqft=buildability.buildable_area_sqft if buildability is not None else None,
        estimated_floors=envelope.estimated_floors if envelope is not None else None,
        finished_comp_prices=[comp.sale_price for comp in finished_comps],
        land_value=land_value if land_value is not None else market_value,
        acquisition_price=acquisition_price,
        land_value_is_assessed=land_value is None and market_value is not None,
    )
    assumptions: DealAssumptions = _assumptions(
        construction_cost_per_sqft=profile_overrides.get("construction_cost_per_sqft"),
        soft_cost_pct=profile_overrides.get("soft_cost_pct"),
        selling_cost_pct=profile_overrides.get("selling_cost_pct"),
        target_margin=profile_overrides.get("target_margin"),
        default_unit_sqft=profile_overrides.get("default_unit_sqft"),
        max_unit_sqft=profile_overrides.get("max_unit_sqft"),
        market_overrides=market_overrides,
    )

    disclosure = mao_disclosure(assumption_set, computed_at)
    return UnderwritingAnalysis(
        assumptions=[
            {
                "name": item.name,
                "group": item.group,
                "value": None if item.value is None else float(item.value),
                "origin": item.origin,
                "unit": item.unit,
                "limitations": item.limitations,
            }
            for item in assumption_set.items.values()
        ],
        mao={
            "formula": disclosure.formula,
            "target_margin": disclosure.target_margin,
            "inputs": disclosure.inputs,
            "exclusions": list(disclosure.exclusions),
            "unavailable_inputs": list(disclosure.unavailable_inputs),
        },
        cases=analyze_cases(inputs, assumptions, computed_at=computed_at),
        sensitivity=build_grid(inputs, assumptions, computed_at=computed_at),
        profile_version=None,
        computed_at=computed_at,
    )
