from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.risk.service import assess_parcel_risk
from lotscope.valuation.service import value_parcel
from lotscope.verdict.composition import ComposedVerdict, compose_verdict
from lotscope.verdict.models import ParcelVerdict
from lotscope.verdict.schemas import VerdictResult
from lotscope.zoning.service import assess_parcel as assess_zoning

_PARCEL_SQL = text("SELECT market_value FROM parcel WHERE parcel_number = :parcel_number")


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


async def _persist(
    session: AsyncSession,
    parcel_number: str,
    composed: ComposedVerdict,
    computed_at: datetime,
) -> None:
    values: dict[str, Any] = {
        **asdict(composed),
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
        risk_score=composed.risk_score,
        risk_flags=composed.risk_flags,
        sources=composed.sources,
        computed_at=computed_at,
    )


async def compute_verdict(session: AsyncSession, parcel_number: str) -> VerdictResult | None:
    parcel = (await session.execute(_PARCEL_SQL, {"parcel_number": parcel_number})).one_or_none()
    if parcel is None:
        return None

    buildability = await assess_zoning(session, parcel_number)
    valuation = await value_parcel(session, parcel_number)
    risk = await assess_parcel_risk(session, parcel_number)
    composed = compose_verdict(
        buildability,
        valuation,
        risk,
        assessed_market_value=_as_float(parcel.market_value),
    )
    computed_at = datetime.now(UTC)
    await _persist(session, parcel_number, composed, computed_at)
    return _to_result(parcel_number, composed, computed_at)


async def recompute_verdicts(session: AsyncSession, parcel_numbers: Sequence[str]) -> int:
    count = 0
    for parcel_number in parcel_numbers:
        if await compute_verdict(session, parcel_number) is not None:
            count += 1
    return count
