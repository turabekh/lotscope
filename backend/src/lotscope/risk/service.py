from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.risk.schemas import (
    NextSheriffSale,
    RiskFlagSchema,
    RiskResult,
    SheriffSaleCalendar,
    SheriffSaleItem,
)
from lotscope.risk.scoring import (
    STREET_ACCESS_MAX_FT,
    AccessSignal,
    HistoricSignal,
    LiSignal,
    OverlaySignal,
    RcoSignal,
    RiskSignals,
    TaxSignal,
    TitleSignal,
    assess_risk,
)

_PARCEL_SQL = text(
    "SELECT is_city_owned, owner, (geom_local IS NOT NULL) AS has_geometry "
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
    "FROM parcel p JOIN flood_zone fz ON ST_Intersects(fz.geom_local, p.geom_local) "
    "WHERE p.parcel_number = :parcel_number AND fz.zone IS NOT NULL"
)
_ACCESS_SQL = text(
    "SELECT EXISTS("
    "SELECT 1 FROM street_centerline s JOIN parcel p ON p.parcel_number = :parcel_number "
    "WHERE ST_DWithin(s.geom_local, p.geom_local, :max)"
    ") AS has_frontage"
)
_HISTORIC_SQL = text(
    "SELECT hd.name FROM parcel p "
    "JOIN historic_district hd ON ST_Intersects(hd.geom_local, p.geom_local) "
    "WHERE p.parcel_number = :parcel_number AND p.geom_local IS NOT NULL "
    "ORDER BY hd.name LIMIT 1"
)
_OVERLAY_SQL = text(
    "SELECT array_agg(DISTINCT zo.name ORDER BY zo.name) AS names FROM parcel p "
    "JOIN zoning_overlay zo ON ST_Intersects(zo.geom_local, p.geom_local) "
    "WHERE p.parcel_number = :parcel_number AND p.geom_local IS NOT NULL AND zo.name IS NOT NULL"
)
_RCO_SQL = text(
    "SELECT array_agg(DISTINCT r.name ORDER BY r.name) AS names FROM parcel p "
    "JOIN rco r ON ST_Intersects(r.geom_local, p.geom_local) "
    "WHERE p.parcel_number = :parcel_number AND p.geom_local IS NOT NULL AND r.name IS NOT NULL"
)

_CHECKED_SOURCES = (
    "tax_status",
    "li_event",
    "flood_zone",
    "street_centerline",
    "historicdistricts_local",
    "zoning_overlays",
    "zoning_rco",
    "parcel",
)


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


async def _historic_signal(session: AsyncSession, parcel_number: str) -> HistoricSignal:
    name = await session.scalar(_HISTORIC_SQL, {"parcel_number": parcel_number})
    return HistoricSignal(in_district=name is not None, district_name=name)


async def _overlay_signal(session: AsyncSession, parcel_number: str) -> OverlaySignal:
    names = await session.scalar(_OVERLAY_SQL, {"parcel_number": parcel_number})
    return OverlaySignal(overlay_names=tuple(names or ()))


async def _rco_signal(session: AsyncSession, parcel_number: str) -> RcoSignal:
    names = await session.scalar(_RCO_SQL, {"parcel_number": parcel_number})
    return RcoSignal(rco_names=tuple(names or ()))


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
    historic = (
        await _historic_signal(session, parcel_number)
        if parcel.has_geometry
        else HistoricSignal(in_district=False)
    )
    overlays = (
        await _overlay_signal(session, parcel_number) if parcel.has_geometry else OverlaySignal()
    )
    rco = await _rco_signal(session, parcel_number) if parcel.has_geometry else RcoSignal()
    assessment = assess_risk(
        RiskSignals(
            li=li,
            tax=tax,
            is_city_owned=parcel.is_city_owned,
            flood_zones=flood_zones,
            title=TitleSignal(owner=parcel.owner),
            access=AccessSignal(has_geometry=parcel.has_geometry, has_street_frontage=has_frontage),
            historic=historic,
            overlays=overlays,
            rco=rco,
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


_SHERIFF_SELECT = (
    "SELECT ss.parcel_number, p.address, ss.case_number, ss.sale_type, ss.sale_date, "
    "ss.status, ss.opening_bid, ss.plaintiff, pv.max_allowable_offer, "
    "(pv.max_allowable_offer - ss.opening_bid) AS bid_gap, "
    "round(pv.opportunity_score)::int AS opportunity_score "
    "FROM sheriff_sale ss "
    "JOIN parcel p ON p.parcel_number = ss.parcel_number "
    "LEFT JOIN parcel_verdict pv ON pv.parcel_number = ss.parcel_number"
)


async def list_sheriff_sales(
    session: AsyncSession,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    zip_code: str | None = None,
    limit: int = 200,
) -> SheriffSaleCalendar:
    conditions: list[str] = []
    params: dict[str, Any] = {"limit": limit}
    if date_from is not None:
        conditions.append("ss.sale_date >= :date_from")
        params["date_from"] = date_from
    if date_to is not None:
        conditions.append("ss.sale_date <= :date_to")
        params["date_to"] = date_to
    if zip_code is not None:
        conditions.append("p.zip_code = :zip_code")
        params["zip_code"] = zip_code
    where = " AND ".join(conditions) if conditions else "TRUE"

    total = await session.scalar(
        text(
            f"SELECT count(*) FROM sheriff_sale ss JOIN parcel p "
            f"ON p.parcel_number = ss.parcel_number WHERE {where}"
        ),
        params,
    )
    rows = (
        await session.execute(
            text(
                f"{_SHERIFF_SELECT} WHERE {where} "
                "ORDER BY bid_gap DESC NULLS LAST, ss.sale_date ASC NULLS LAST, ss.id "
                "LIMIT :limit"
            ),
            params,
        )
    ).all()
    items = [
        SheriffSaleItem(
            parcel_number=row.parcel_number,
            address=row.address,
            case_number=row.case_number,
            sale_type=row.sale_type,
            sale_date=row.sale_date,
            status=row.status,
            opening_bid=_as_float(row.opening_bid),
            plaintiff=row.plaintiff,
            max_allowable_offer=_as_float(row.max_allowable_offer),
            bid_gap=_as_float(row.bid_gap),
            opportunity_score=row.opportunity_score,
        )
        for row in rows
    ]
    return SheriffSaleCalendar(total=int(total or 0), returned=len(items), items=items)


_NEXT_SHERIFF_SALE_SQL = text(
    "SELECT case_number, sale_type, sale_date, status, opening_bid "
    "FROM sheriff_sale "
    "WHERE parcel_number = :parcel_number AND sale_date IS NOT NULL AND sale_date >= :today "
    "ORDER BY sale_date ASC, id ASC LIMIT 1"
)


async def get_next_sheriff_sale(
    session: AsyncSession, parcel_number: str, *, today: date | None = None
) -> NextSheriffSale | None:
    as_of = today or datetime.now(UTC).date()
    row = (
        await session.execute(
            _NEXT_SHERIFF_SALE_SQL, {"parcel_number": parcel_number, "today": as_of}
        )
    ).one_or_none()
    if row is None:
        return None
    return NextSheriffSale(
        parcel_number=parcel_number,
        case_number=row.case_number,
        sale_type=row.sale_type,
        sale_date=row.sale_date,
        status=row.status,
        opening_bid=_as_float(row.opening_bid),
        days_until=(row.sale_date - as_of).days,
    )
