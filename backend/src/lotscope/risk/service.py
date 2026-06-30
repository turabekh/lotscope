from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.risk.schemas import RiskFlagSchema, RiskResult
from lotscope.risk.scoring import (
    STREET_ACCESS_MAX_FT,
    AccessSignal,
    LiSignal,
    RiskSignals,
    TaxSignal,
    TitleSignal,
    assess_risk,
)

_PARCEL_SQL = text(
    "SELECT is_city_owned, owner, (geom_2272 IS NOT NULL) AS has_geometry "
    "FROM parcel WHERE parcel_number = :parcel_number"
)
_TAX_SQL = text(
    "SELECT is_delinquent, total_due, years_owed, in_sheriff_sale "
    "FROM tax_status WHERE parcel_number = :parcel_number"
)
_LI_SQL = text(
    "SELECT count(*) FILTER (WHERE event_type = 'violation') AS violations, "
    "count(*) FILTER (WHERE event_type = 'violation' AND upper(coalesce(status, '')) = 'OPEN') "
    "AS open_violations, "
    "coalesce(bool_or(coalesce(is_unsafe, false)), false) AS has_unsafe, "
    "coalesce(bool_or(coalesce(is_imminently_dangerous, false)), false) "
    "AS has_imminently_dangerous, "
    "count(*) FILTER (WHERE event_type = 'demolition') AS demolitions "
    "FROM li_event WHERE parcel_number = :parcel_number"
)
_LI_TYPES_SQL = text(
    "SELECT description FROM li_event "
    "WHERE parcel_number = :parcel_number AND event_type = 'violation' "
    "AND description IS NOT NULL "
    "GROUP BY description ORDER BY count(*) DESC, description LIMIT 4"
)
_FLOOD_SQL = text(
    "SELECT array_agg(DISTINCT fz.zone) AS zones "
    "FROM parcel p JOIN flood_zone fz ON ST_Intersects(fz.geom_2272, p.geom_2272) "
    "WHERE p.parcel_number = :parcel_number AND fz.zone IS NOT NULL"
)
_ACCESS_SQL = text(
    "SELECT EXISTS("
    "SELECT 1 FROM street_centerline s JOIN parcel p ON p.parcel_number = :parcel_number "
    "WHERE ST_DWithin(s.geom_2272, p.geom_2272, :max)"
    ") AS has_frontage"
)

_CHECKED_SOURCES = ("tax_status", "li_event", "flood_zone", "street_centerline", "parcel")


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


async def _tax_signal(session: AsyncSession, parcel_number: str) -> TaxSignal | None:
    row = (await session.execute(_TAX_SQL, {"parcel_number": parcel_number})).one_or_none()
    if row is None:
        return None
    return TaxSignal(
        is_delinquent=row.is_delinquent,
        total_due=_as_float(row.total_due),
        years_owed=row.years_owed,
        in_sheriff_sale=row.in_sheriff_sale,
    )


async def _li_signal(session: AsyncSession, parcel_number: str) -> LiSignal:
    row = (await session.execute(_LI_SQL, {"parcel_number": parcel_number})).one()
    types = (await session.execute(_LI_TYPES_SQL, {"parcel_number": parcel_number})).scalars().all()
    return LiSignal(
        violations=row.violations,
        has_unsafe=row.has_unsafe,
        has_imminently_dangerous=row.has_imminently_dangerous,
        demolitions=row.demolitions,
        open_violations=row.open_violations,
        violation_types=tuple(types),
    )


async def _flood_zones(session: AsyncSession, parcel_number: str) -> list[str]:
    zones = await session.scalar(_FLOOD_SQL, {"parcel_number": parcel_number})
    return [zone for zone in (zones or []) if zone]


async def _has_street_frontage(session: AsyncSession, parcel_number: str) -> bool:
    has_frontage = await session.scalar(
        _ACCESS_SQL, {"parcel_number": parcel_number, "max": STREET_ACCESS_MAX_FT}
    )
    return bool(has_frontage)


async def assess_parcel_risk(session: AsyncSession, parcel_number: str) -> RiskResult | None:
    parcel = (await session.execute(_PARCEL_SQL, {"parcel_number": parcel_number})).one_or_none()
    if parcel is None:
        return None
    computed_at = datetime.now(UTC)

    tax = await _tax_signal(session, parcel_number)
    li = await _li_signal(session, parcel_number)
    flood_zones = await _flood_zones(session, parcel_number) if parcel.has_geometry else []
    has_frontage = (
        await _has_street_frontage(session, parcel_number) if parcel.has_geometry else False
    )
    assessment = assess_risk(
        RiskSignals(
            li=li,
            tax=tax,
            is_city_owned=parcel.is_city_owned,
            flood_zones=flood_zones,
            title=TitleSignal(owner=parcel.owner),
            access=AccessSignal(
                has_geometry=parcel.has_geometry, has_street_frontage=has_frontage
            ),
        )
    )
    return RiskResult(
        parcel_number=parcel_number,
        risk_score=assessment.risk_score,
        flags=[
            RiskFlagSchema(
                code=flag.code,
                severity=flag.severity,
                label=flag.label,
                detail=flag.detail,
                source=flag.source,
            )
            for flag in assessment.flags
        ],
        summary=assessment.summary,
        confidence=assessment.confidence,
        sources=[{"source": source} for source in _CHECKED_SOURCES],
        computed_at=computed_at,
    )
