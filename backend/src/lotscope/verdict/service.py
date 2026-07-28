from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.logging import get_logger
from lotscope.deal.service import build_deal
from lotscope.ingestion.service import dataset_last_success, source_as_of
from lotscope.risk.service import assess_parcel_risk
from lotscope.valuation.service import value_parcel
from lotscope.verdict.composition import VERDICT_VERSION, ComposedVerdict, compose_verdict
from lotscope.verdict.models import ParcelVerdict
from lotscope.verdict.schemas import VerdictResult
from lotscope.zoning.service import assess_parcel as assess_zoning

_logger = get_logger("verdict.service")

_PARCEL_SQL = text(
    "SELECT market_value, base_zoning_code, market_code FROM parcel "
    "WHERE parcel_number = :parcel_number"
)

_DEAL_SIGNALS_SQL = text(
    "SELECT parcel_number, deal_score, max_allowable_offer, is_underpriced "
    "FROM parcel_verdict WHERE parcel_number = ANY(:parcel_numbers)"
)


@dataclass(frozen=True)
class DealSignal:
    deal_score: float | None
    max_allowable_offer: float | None
    is_underpriced: bool | None


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


async def get_deal_signals(
    session: AsyncSession, parcel_numbers: Sequence[str]
) -> dict[str, DealSignal]:
    if not parcel_numbers:
        return {}
    rows = (
        await session.execute(_DEAL_SIGNALS_SQL, {"parcel_numbers": list(parcel_numbers)})
    ).all()
    return {
        row.parcel_number: DealSignal(
            deal_score=_as_float(row.deal_score),
            max_allowable_offer=_as_float(row.max_allowable_offer),
            is_underpriced=row.is_underpriced,
        )
        for row in rows
    }


_DERIVED_ONLY = frozenset({"field_trust"})

_TRUSTED_SOURCE_LABELS = (
    "parcel",
    "pwd_parcel",
    "opa_properties_public",
    "zoning_district",
    "rtt_summary",
    "tax_status",
    "li_event",
    "flood_zone",
    "street_centerline",
)


async def _source_ages(session: AsyncSession, market_code: str) -> dict[str, datetime | None]:
    last_success = await dataset_last_success(session, market_code)
    return {label: source_as_of(label, last_success) for label in _TRUSTED_SOURCE_LABELS}


async def _persist(
    session: AsyncSession,
    parcel_number: str,
    composed: ComposedVerdict,
    computed_at: datetime,
) -> None:
    persisted = {key: value for key, value in asdict(composed).items() if key not in _DERIVED_ONLY}
    values: dict[str, Any] = {
        **persisted,
        "parcel_number": parcel_number,
        "computed_at": computed_at,
    }
    statement = insert(ParcelVerdict).values(values)
    assignments: dict[str, Any] = {
        column: statement.excluded[column] for column in values if column != "parcel_number"
    }
    assignments["updated_at"] = func.now()
    statement = statement.on_conflict_do_update(index_elements=["parcel_number"], set_=assignments)
    await session.execute(statement)


def _to_result(
    parcel_number: str, composed: ComposedVerdict, computed_at: datetime
) -> VerdictResult:
    return VerdictResult(
        parcel_number=parcel_number,
        verdict_version=composed.verdict_version,
        buildability_score=composed.buildability_score,
        opportunity_score=composed.opportunity_score,
        summary=composed.summary,
        can_build_by_right=composed.can_build_by_right,
        by_right_units=composed.by_right_units,
        max_height_ft=composed.max_height_ft,
        needs_variance=composed.needs_variance,
        buildable_area_sqft=composed.buildable_area_sqft,
        value_estimate_low=composed.value_estimate_low,
        value_estimate_high=composed.value_estimate_high,
        value_confidence=composed.value_confidence,
        assessment_market_gap=composed.assessment_market_gap,
        arv=composed.arv,
        est_profit=composed.est_profit,
        est_margin=composed.est_margin,
        max_allowable_offer=composed.max_allowable_offer,
        deal_score=composed.deal_score,
        is_underpriced=composed.is_underpriced,
        risk_score=composed.risk_score,
        risk_flags=composed.risk_flags,
        sources=composed.sources,
        field_trust=composed.field_trust,
        computed_at=computed_at,
    )


async def get_verdict(session: AsyncSession, parcel_number: str) -> VerdictResult | None:
    row = await session.get(ParcelVerdict, parcel_number)
    if row is None:
        return None
    return VerdictResult.model_validate(row)


async def get_or_compute_current_verdict(
    session: AsyncSession, parcel_number: str
) -> VerdictResult | None:
    verdict = await get_verdict(session, parcel_number)
    if verdict is not None and verdict.verdict_version == VERDICT_VERSION:
        return verdict
    return await compute_verdict(session, parcel_number)


async def compute_verdict(session: AsyncSession, parcel_number: str) -> VerdictResult | None:
    parcel = (await session.execute(_PARCEL_SQL, {"parcel_number": parcel_number})).one_or_none()
    if parcel is None:
        return None

    buildability = await assess_zoning(session, parcel_number)
    valuation = await value_parcel(session, parcel_number)
    risk = await assess_parcel_risk(session, parcel_number)
    deal = await build_deal(
        session,
        parcel_number,
        base_zoning_code=parcel.base_zoning_code,
        market_value=_as_float(parcel.market_value),
        buildability=buildability,
        valuation=valuation,
    )
    composed = compose_verdict(
        buildability,
        valuation,
        risk,
        deal,
        assessed_market_value=_as_float(parcel.market_value),
        source_ages=await _source_ages(session, parcel.market_code),
    )
    computed_at = datetime.now(UTC)
    await _persist(session, parcel_number, composed, computed_at)
    return _to_result(parcel_number, composed, computed_at)


async def recompute_verdicts(session: AsyncSession, parcel_numbers: Sequence[str]) -> int:
    count = 0
    for parcel_number in parcel_numbers:
        try:
            async with session.begin_nested():
                if await compute_verdict(session, parcel_number) is not None:
                    count += 1
        except Exception as error:
            _logger.warning(
                "verdict_recompute_skipped", parcel_number=parcel_number, error=str(error)
            )
    return count
