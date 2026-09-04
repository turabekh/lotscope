from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.buybox.service import buy_box_assumptions
from lotscope.core.config import get_settings
from lotscope.core.logging import get_logger
from lotscope.deal.analysis import DealAssumptions, DealInputs, analyze_deal
from lotscope.deal.scenarios import ScenarioInputs, build_scenarios
from lotscope.deal.schemas import (
    DealAssumptionsSchema,
    DealResult,
    ScenarioItem,
    ScenariosResult,
)
from lotscope.valuation.avm import land_use_class
from lotscope.valuation.schemas import ValuationResult
from lotscope.valuation.service import find_comps, value_parcel
from lotscope.zoning.schemas import BuildabilityResult
from lotscope.zoning.service import assess_parcel as assess_zoning
from lotscope.zoning.service import compute_envelope

_SUBJECT_SQL = text(
    "SELECT market_value, base_zoning_code FROM parcel WHERE parcel_number = :parcel_number"
)
logger = get_logger(__name__)


def assumptions_source(assumptions: dict[str, float] | None) -> str:
    return "buy_box" if assumptions else "platform_default"


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def _assumptions(
    *,
    construction_cost_per_sqft: float | None = None,
    soft_cost_pct: float | None = None,
    selling_cost_pct: float | None = None,
    target_margin: float | None = None,
    default_unit_sqft: float | None = None,
    max_unit_sqft: float | None = None,
    buy_box: dict[str, float] | None = None,
) -> DealAssumptions:
    settings = get_settings()
    chosen = buy_box or {}

    def resolve(requested: float | None, key: str, platform: float) -> float:
        if requested is not None:
            return requested
        if key in chosen:
            return chosen[key]
        return platform

    return DealAssumptions(
        construction_cost_per_sqft=resolve(
            construction_cost_per_sqft,
            "construction_cost_per_sqft",
            settings.deal_construction_cost_per_sqft,
        ),
        soft_cost_pct=resolve(soft_cost_pct, "soft_cost_pct", settings.deal_soft_cost_pct),
        selling_cost_pct=resolve(
            selling_cost_pct, "selling_cost_pct", settings.deal_selling_cost_pct
        ),
        target_margin=resolve(target_margin, "target_margin", settings.deal_target_margin),
        default_unit_sqft=resolve(
            default_unit_sqft, "default_unit_sqft", settings.deal_default_unit_sqft
        ),
        max_unit_sqft=resolve(max_unit_sqft, "max_unit_sqft", settings.deal_max_unit_sqft),
    )


async def analyze_parcel_deal(
    session: AsyncSession,
    parcel_number: str,
    *,
    user_id: int | None = None,
    acquisition_price: float | None = None,
    construction_cost_per_sqft: float | None = None,
    soft_cost_pct: float | None = None,
    selling_cost_pct: float | None = None,
    target_margin: float | None = None,
    radius_ft: float = 1500.0,
    years: int = 3,
) -> DealResult | None:
    subject = (await session.execute(_SUBJECT_SQL, {"parcel_number": parcel_number})).one_or_none()
    if subject is None:
        return None

    buildability = await assess_zoning(session, parcel_number)
    valuation = await value_parcel(session, parcel_number, radius_ft=radius_ft, years=years)
    return await build_deal(
        session,
        parcel_number,
        user_id=user_id,
        base_zoning_code=subject.base_zoning_code,
        market_value=_as_float(subject.market_value),
        buildability=buildability,
        valuation=valuation,
        acquisition_price=acquisition_price,
        construction_cost_per_sqft=construction_cost_per_sqft,
        soft_cost_pct=soft_cost_pct,
        selling_cost_pct=selling_cost_pct,
        target_margin=target_margin,
        radius_ft=radius_ft,
        years=years,
    )


async def analyze_parcel_scenarios(
    session: AsyncSession,
    parcel_number: str,
    *,
    user_id: int | None = None,
    acquisition_price: float | None = None,
    construction_cost_per_sqft: float | None = None,
    soft_cost_pct: float | None = None,
    selling_cost_pct: float | None = None,
    target_margin: float | None = None,
    radius_ft: float = 1500.0,
    years: int = 3,
) -> ScenariosResult | None:
    subject = (await session.execute(_SUBJECT_SQL, {"parcel_number": parcel_number})).one_or_none()
    if subject is None:
        return None
    computed_at = datetime.now(UTC)

    buildability = await assess_zoning(session, parcel_number)
    valuation = await value_parcel(session, parcel_number, radius_ft=radius_ft, years=years)
    envelope = await compute_envelope(session, parcel_number)

    use_class = land_use_class(subject.base_zoning_code)
    finished_comps, _ = await find_comps(
        session,
        parcel_number,
        radius_ft=radius_ft,
        years=years,
        vacant_only=False,
        use_class=use_class,
    )
    finished_prices = [comp.sale_price for comp in finished_comps]

    land_value = valuation.estimate if valuation is not None else None
    land_value_is_assessed = False
    if acquisition_price is None and land_value is None:
        land_value = _as_float(subject.market_value)
        land_value_is_assessed = land_value is not None

    buy_box = await buy_box_assumptions(session, user_id)
    assumptions = _assumptions(
        construction_cost_per_sqft=construction_cost_per_sqft,
        soft_cost_pct=soft_cost_pct,
        selling_cost_pct=selling_cost_pct,
        target_margin=target_margin,
        buy_box=buy_box,
    )
    analysis = build_scenarios(
        ScenarioInputs(
            by_right_units=buildability.by_right_units if buildability is not None else None,
            buildable_area_sqft=buildability.buildable_area_sqft
            if buildability is not None
            else None,
            estimated_floors=envelope.estimated_floors if envelope is not None else None,
            finished_comp_prices=finished_prices,
            land_value=land_value,
            acquisition_price=acquisition_price,
            land_value_is_assessed=land_value_is_assessed,
        ),
        assumptions,
    )
    return ScenariosResult(
        parcel_number=parcel_number,
        by_right_units=analysis.by_right_units,
        recommended_units=analysis.recommended_units,
        scenarios=[
            ScenarioItem(
                units=scenario.units,
                by_right=scenario.by_right,
                arv=scenario.arv,
                total_cost=scenario.total_cost,
                profit=scenario.profit,
                margin=scenario.margin,
                roi=scenario.roi,
                max_allowable_offer=scenario.max_allowable_offer,
                deal_score=scenario.deal_score,
                infeasible=scenario.infeasible,
            )
            for scenario in analysis.scenarios
        ],
        confidence=analysis.confidence,
        assumptions=DealAssumptionsSchema(
            construction_cost_per_sqft=assumptions.construction_cost_per_sqft,
            soft_cost_pct=assumptions.soft_cost_pct,
            selling_cost_pct=assumptions.selling_cost_pct,
            target_margin=assumptions.target_margin,
            default_unit_sqft=assumptions.default_unit_sqft,
            max_unit_sqft=assumptions.max_unit_sqft,
        ),
        reasons=analysis.reasons,
        sources=[
            {
                "dimension": "scenarios",
                "arv_comps": len(finished_comps),
                "radius_ft": radius_ft,
                "years": years,
                "use_class": use_class,
            }
        ],
        computed_at=computed_at,
    )


async def build_deal(
    session: AsyncSession,
    parcel_number: str,
    *,
    user_id: int | None = None,
    base_zoning_code: str | None,
    market_value: float | None,
    buildability: BuildabilityResult | None,
    valuation: ValuationResult | None,
    acquisition_price: float | None = None,
    construction_cost_per_sqft: float | None = None,
    soft_cost_pct: float | None = None,
    selling_cost_pct: float | None = None,
    target_margin: float | None = None,
    radius_ft: float = 1500.0,
    years: int = 3,
) -> DealResult:
    computed_at = datetime.now(UTC)

    envelope = await compute_envelope(session, parcel_number)

    use_class = land_use_class(base_zoning_code)
    finished_comps, _ = await find_comps(
        session,
        parcel_number,
        radius_ft=radius_ft,
        years=years,
        vacant_only=False,
        use_class=use_class,
    )
    finished_prices = [comp.sale_price for comp in finished_comps]

    units = buildability.by_right_units if buildability is not None else None
    land_value = valuation.estimate if valuation is not None else None
    land_value_is_assessed = False
    if acquisition_price is None and land_value is None:
        land_value = market_value
        land_value_is_assessed = land_value is not None

    buy_box = await buy_box_assumptions(session, user_id)
    assumptions = _assumptions(
        construction_cost_per_sqft=construction_cost_per_sqft,
        soft_cost_pct=soft_cost_pct,
        selling_cost_pct=selling_cost_pct,
        target_margin=target_margin,
        buy_box=buy_box,
    )
    analysis = analyze_deal(
        DealInputs(
            units=units,
            buildable_area_sqft=buildability.buildable_area_sqft
            if buildability is not None
            else None,
            estimated_floors=envelope.estimated_floors if envelope is not None else None,
            finished_comp_prices=finished_prices,
            land_value=land_value,
            acquisition_price=acquisition_price,
            land_value_is_assessed=land_value_is_assessed,
        ),
        assumptions,
    )

    return DealResult(
        parcel_number=parcel_number,
        assumptions_source=assumptions_source(buy_box),
        units=units,
        arv=analysis.arv,
        per_unit_value=analysis.per_unit_value,
        gross_floor_area_sqft=analysis.gross_floor_area_sqft,
        acquisition_cost=analysis.acquisition_cost,
        construction_cost=analysis.construction_cost,
        soft_cost=analysis.soft_cost,
        selling_cost=analysis.selling_cost,
        total_cost=analysis.total_cost,
        profit=analysis.profit,
        margin=analysis.margin,
        roi=analysis.roi,
        max_allowable_offer=analysis.max_allowable_offer,
        is_underpriced=analysis.is_underpriced,
        deal_score=analysis.deal_score,
        infeasible=analysis.infeasible,
        comp_count=analysis.comp_count,
        confidence=analysis.confidence,
        assumptions=DealAssumptionsSchema(
            construction_cost_per_sqft=assumptions.construction_cost_per_sqft,
            soft_cost_pct=assumptions.soft_cost_pct,
            selling_cost_pct=assumptions.selling_cost_pct,
            target_margin=assumptions.target_margin,
            default_unit_sqft=assumptions.default_unit_sqft,
            max_unit_sqft=assumptions.max_unit_sqft,
        ),
        reasons=analysis.reasons,
        sources=[
            {
                "dimension": "deal",
                "arv_comps": len(finished_comps),
                "radius_ft": radius_ft,
                "years": years,
                "use_class": use_class,
                "land_value_source": "avm" if valuation is not None else "assessment",
            }
        ],
        computed_at=computed_at,
    )
