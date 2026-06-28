from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import get_settings
from lotscope.deal.analysis import DealAssumptions, DealInputs, analyze_deal
from lotscope.deal.schemas import DealAssumptionsSchema, DealResult
from lotscope.valuation.avm import land_use_class
from lotscope.valuation.schemas import ValuationResult
from lotscope.valuation.service import find_comps, value_parcel
from lotscope.zoning.schemas import BuildabilityResult
from lotscope.zoning.service import assess_parcel as assess_zoning
from lotscope.zoning.service import compute_envelope

_SUBJECT_SQL = text(
    "SELECT market_value, base_zoning_code FROM parcel WHERE parcel_number = :parcel_number"
)


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def _assumptions(
    *,
    construction_cost_per_sqft: float | None,
    soft_cost_pct: float | None,
    selling_cost_pct: float | None,
    target_margin: float | None,
) -> DealAssumptions:
    settings = get_settings()
    return DealAssumptions(
        construction_cost_per_sqft=construction_cost_per_sqft
        if construction_cost_per_sqft is not None
        else settings.deal_construction_cost_per_sqft,
        soft_cost_pct=soft_cost_pct if soft_cost_pct is not None else settings.deal_soft_cost_pct,
        selling_cost_pct=selling_cost_pct
        if selling_cost_pct is not None
        else settings.deal_selling_cost_pct,
        target_margin=target_margin if target_margin is not None else settings.deal_target_margin,
        default_unit_sqft=settings.deal_default_unit_sqft,
    )


async def analyze_parcel_deal(
    session: AsyncSession,
    parcel_number: str,
    *,
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


async def build_deal(
    session: AsyncSession,
    parcel_number: str,
    *,
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
    finished_comps = await find_comps(
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
    if acquisition_price is None and land_value is None:
        land_value = market_value

    assumptions = _assumptions(
        construction_cost_per_sqft=construction_cost_per_sqft,
        soft_cost_pct=soft_cost_pct,
        selling_cost_pct=selling_cost_pct,
        target_margin=target_margin,
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
        ),
        assumptions,
    )

    return DealResult(
        parcel_number=parcel_number,
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
        comp_count=analysis.comp_count,
        confidence=analysis.confidence,
        assumptions=DealAssumptionsSchema(
            construction_cost_per_sqft=assumptions.construction_cost_per_sqft,
            soft_cost_pct=assumptions.soft_cost_pct,
            selling_cost_pct=assumptions.selling_cost_pct,
            target_margin=assumptions.target_margin,
            default_unit_sqft=assumptions.default_unit_sqft,
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
