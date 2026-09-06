from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.buybox.service import buy_box_assumptions
from lotscope.core.config import get_settings
from lotscope.deal.schemas import DealResult
from lotscope.deal.service import build_deal
from lotscope.ingestion.service import dataset_last_success, source_as_of
from lotscope.risk.service import assess_parcel_risk
from lotscope.valuation.schemas import ValuationResult
from lotscope.valuation.service import value_parcel
from lotscope.verdict import cache
from lotscope.verdict.composition import ComposedVerdict, compose_verdict
from lotscope.verdict.schemas import VerdictResult
from lotscope.zoning.schemas import BuildabilityResult
from lotscope.zoning.service import assess_parcel as assess_zoning

_PARCEL_SQL = text(
    "SELECT market_value, base_zoning_code, market_code FROM parcel "
    "WHERE parcel_number = :parcel_number"
)

# The nightly screening index, not the verdict. Search ranks on it and the buy box
# pre-filters on it; nothing here is ever the answer a user reads.
_DEAL_SIGNALS_SQL = text(
    "SELECT parcel_number, deal_score, max_allowable_offer, is_underpriced "
    "FROM parcel_screen WHERE parcel_number = ANY(:parcel_numbers)"
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


def _to_result(
    parcel_number: str, composed: ComposedVerdict, computed_at: datetime
) -> VerdictResult:
    return VerdictResult(
        parcel_number=parcel_number,
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
        recommendation=composed.recommendation,
        recommendation_reason=composed.recommendation_reason,
        computed_at=computed_at,
    )


class VerdictRead(BaseModel):
    """The verdict and the working behind it.

    The packet needs the buildability and the deal themselves — the sensitivity grid is
    built from the deal's own inputs, which the composed verdict flattens away. Rather
    than let the packet compose its own copy beside this one, the read carries both.
    """

    verdict: VerdictResult
    buildability: BuildabilityResult | None = None
    valuation: ValuationResult | None = None
    deal: DealResult | None = None


async def compute_verdict_read(
    session: AsyncSession, parcel_number: str, *, user_id: int | None = None
) -> VerdictRead | None:
    """The verdict from the inputs as they stand right now. Nothing is written.

    A user id brings that buyer's own underwriting assumptions to the deal; without one
    the platform defaults apply, which is what every shared surface reads.
    """
    parcel = (await session.execute(_PARCEL_SQL, {"parcel_number": parcel_number})).one_or_none()
    if parcel is None:
        return None

    buildability = await assess_zoning(session, parcel_number)
    valuation = await value_parcel(session, parcel_number)
    risk = await assess_parcel_risk(session, parcel_number)
    deal = await build_deal(
        session,
        parcel_number,
        user_id=user_id,
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
    return VerdictRead(
        verdict=_to_result(parcel_number, composed, datetime.now(UTC)),
        buildability=buildability,
        valuation=valuation,
        deal=deal,
    )


async def compute_verdict(
    session: AsyncSession, parcel_number: str, *, user_id: int | None = None
) -> VerdictResult | None:
    read = await compute_verdict_read(session, parcel_number, user_id=user_id)
    return read.verdict if read is not None else None


async def get_verdict_read(
    session: AsyncSession,
    parcel_number: str,
    *,
    redis: Redis | None = None,
    user_id: int | None = None,
) -> VerdictRead | None:
    """The verdict on a parcel and its working, computed when it is read.

    With Redis the read is cached for a day against a fingerprint of its inputs — which
    includes the buyer's own assumptions, so a buyer who has changed none shares the
    entry with everyone else and one who has changed them does not read theirs.
    """
    if redis is None:
        return await compute_verdict_read(session, parcel_number, user_id=user_id)

    assumptions = await buy_box_assumptions(session, user_id) if user_id is not None else {}
    fingerprint = await cache.input_fingerprint(
        session, parcel_number, git_sha=get_settings().git_sha, assumptions=assumptions
    )
    if fingerprint is None:
        return None

    cached = await cache.read(redis, parcel_number, fingerprint)
    if cached is not None:
        return cached

    read = await compute_verdict_read(session, parcel_number, user_id=user_id)
    if read is not None:
        await cache.write(redis, parcel_number, fingerprint, read)
    return read


async def get_verdict(
    session: AsyncSession,
    parcel_number: str,
    *,
    redis: Redis | None = None,
    user_id: int | None = None,
) -> VerdictResult | None:
    read = await get_verdict_read(session, parcel_number, redis=redis, user_id=user_id)
    return read.verdict if read is not None else None
