from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import get_settings
from lotscope.deal.service import build_deal
from lotscope.ingestion.service import dataset_last_success, source_as_of
from lotscope.risk.service import assess_parcel_risk
from lotscope.valuation.service import value_parcel
from lotscope.verdict import cache
from lotscope.verdict.composition import ComposedVerdict, compose_verdict
from lotscope.verdict.schemas import VerdictResult
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


async def compute_verdict(session: AsyncSession, parcel_number: str) -> VerdictResult | None:
    """The verdict from the inputs as they stand right now. Nothing is written."""
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
    return _to_result(parcel_number, composed, datetime.now(UTC))


async def get_verdict(
    session: AsyncSession, parcel_number: str, *, redis: Redis | None = None
) -> VerdictResult | None:
    """The verdict on a parcel, computed when it is read.

    With Redis the result is cached for a day against a fingerprint of its inputs, so a
    second read costs one query rather than the whole composition, and an input that has
    moved since is a miss rather than a stale answer. Without Redis it is simply computed.
    """
    if redis is None:
        return await compute_verdict(session, parcel_number)

    fingerprint = await cache.input_fingerprint(
        session, parcel_number, git_sha=get_settings().git_sha
    )
    if fingerprint is None:
        return None

    cached = await cache.read(redis, parcel_number, fingerprint)
    if cached is not None:
        return cached

    verdict = await compute_verdict(session, parcel_number)
    if verdict is not None:
        await cache.write(redis, parcel_number, fingerprint, verdict)
    return verdict
