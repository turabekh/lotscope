from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.market import MARKET_CODE
from lotscope.risk.attribution import TransferAfterSnapshot, attribute_delinquency
from lotscope.risk.schemas import (
    NextSheriffSale,
    RiskFlagSchema,
    RiskResult,
    SheriffSaleCalendar,
    SheriffSaleChange,
    SheriffSaleDate,
    SheriffSaleDates,
    SheriffSaleItem,
    ViolationPosture,
)
from lotscope.risk.scoring import (
    STREET_ACCESS_MAX_FT,
    AccessSignal,
    HistoricSignal,
    LiSignal,
    OverlaySignal,
    RcoSignal,
    RiskFlag,
    RiskSignals,
    TaxSignal,
    TitleSignal,
    assess_risk,
)
from lotscope.risk.violation_status import open_violation_sql

_PARCEL_SQL = text(
    "SELECT is_city_owned, owner, (geom_local IS NOT NULL) AS has_geometry "
    "FROM parcel WHERE parcel_number = :parcel_number"
)
_TAX_SQL = text(
    "SELECT ts.is_delinquent, ts.total_due, ts.years_owed, ts.in_sheriff_sale, "
    "ts.delinquency_owner, ts.snapshot_period, p.owner AS current_owner, "
    "d.grantor, d.document_type, d.document_id, d.sale_date, d.sale_price "
    "FROM tax_status ts "
    "JOIN parcel p ON p.parcel_number = ts.parcel_number "
    "LEFT JOIN LATERAL ("
    "  SELECT s.grantor, s.document_type, s.document_id, s.sale_date, s.sale_price "
    "  FROM sale s WHERE s.parcel_number = ts.parcel_number "
    "  AND ts.snapshot_period IS NOT NULL "
    "  AND s.sale_date >= (to_date(ts.snapshot_period, 'YYYYMM') + interval '1 month')::date "
    "  ORDER BY s.sale_date ASC LIMIT 1"
    ") d ON TRUE "
    "WHERE ts.parcel_number = :parcel_number"
)
_LI_SQL = text(
    "SELECT count(*) FILTER (WHERE event_type = 'violation') AS violations, "
    "count(*) FILTER (WHERE event_type = 'violation' AND "
    + open_violation_sql("li_event")
    + ") AS open_violations, "
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
    "FROM parcel p JOIN flood_zone fz ON fz.market_code = p.market_code "
    "AND ST_Intersects(fz.geom_local, p.geom_local) "
    "WHERE p.parcel_number = :parcel_number AND fz.zone IS NOT NULL"
)
_ACCESS_SQL = text(
    "SELECT EXISTS("
    "SELECT 1 FROM street_centerline s JOIN parcel p ON p.parcel_number = :parcel_number "
    "WHERE s.market_code = p.market_code AND ST_DWithin(s.geom_local, p.geom_local, :max)"
    ") AS has_frontage"
)
_MARKET_STREETS_SQL = text(
    "SELECT EXISTS("
    "SELECT 1 FROM street_centerline s JOIN parcel p ON p.parcel_number = :parcel_number "
    "WHERE s.market_code = p.market_code"
    ") AS has_streets"
)
_HISTORIC_SQL = text(
    "SELECT hd.name FROM parcel p "
    "JOIN historic_district hd ON hd.market_code = p.market_code "
    "AND ST_Intersects(hd.geom_local, p.geom_local) "
    "WHERE p.parcel_number = :parcel_number AND p.geom_local IS NOT NULL "
    "ORDER BY hd.name LIMIT 1"
)
_OVERLAY_SQL = text(
    "SELECT array_agg(DISTINCT zo.name ORDER BY zo.name) AS names FROM parcel p "
    "JOIN zoning_overlay zo ON zo.market_code = p.market_code "
    "AND ST_Intersects(zo.geom_local, p.geom_local) "
    "WHERE p.parcel_number = :parcel_number AND p.geom_local IS NOT NULL AND zo.name IS NOT NULL"
)
_RCO_SQL = text(
    "SELECT array_agg(DISTINCT r.name ORDER BY r.name) AS names FROM parcel p "
    "JOIN rco r ON r.market_code = p.market_code "
    "AND ST_Intersects(r.geom_local, p.geom_local) "
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


NOT_SCHEDULED_STATUSES = frozenset({"Sold", "Withdrawn", "Stayed", "Cancelled"})

OBSERVED_SHERIFF_STATUSES = frozenset(
    {
        "",
        "Postponed",
        "Scheduled - City Tax",
        "Scheduled - Mortgage Foreclosure",
        "Scheduled - Tax",
    }
)

SHERIFF_SALE_SURFACE_LABEL = "Sheriff sales"
_NO_UPCOMING_SALES_NOTE = (
    "No upcoming sheriff sales are currently loaded for Philadelphia. Lists publish on a "
    "rolling basis — check back or watch individual parcels."
)


def _flag_schema(flag: RiskFlag) -> RiskFlagSchema:
    return RiskFlagSchema(
        code=flag.code,
        severity=flag.severity,
        label=flag.label,
        detail=flag.detail,
        source=flag.source,
    )


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


async def _tax_signal(session: AsyncSession, parcel_number: str) -> TaxSignal | None:
    row = (await session.execute(_TAX_SQL, {"parcel_number": parcel_number})).one_or_none()
    if row is None:
        return None
    transfer = (
        TransferAfterSnapshot(
            grantor=row.grantor,
            document_type=row.document_type,
            document_id=row.document_id,
            sale_date=row.sale_date,
            sale_price=_as_float(row.sale_price),
        )
        if row.document_id is not None
        else None
    )
    return TaxSignal(
        is_delinquent=row.is_delinquent,
        total_due=_as_float(row.total_due),
        years_owed=row.years_owed,
        in_sheriff_sale=row.in_sheriff_sale,
        attribution=attribute_delinquency(
            delinquency_owner=row.delinquency_owner,
            current_owner=row.current_owner,
            snapshot_period=row.snapshot_period,
            transfer=transfer,
        ),
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


async def get_violation_posture(session: AsyncSession, parcel_number: str) -> ViolationPosture:
    signal = await _li_signal(session, parcel_number)
    return ViolationPosture(
        parcel_number=parcel_number,
        violations_on_record=signal.violations,
        open_violations=signal.open_violations,
    )


async def _flood_zones(session: AsyncSession, parcel_number: str) -> list[str]:
    zones = await session.scalar(_FLOOD_SQL, {"parcel_number": parcel_number})
    return [zone for zone in (zones or []) if zone]


async def _has_street_frontage(session: AsyncSession, parcel_number: str) -> bool:
    has_frontage = await session.scalar(
        _ACCESS_SQL, {"parcel_number": parcel_number, "max": STREET_ACCESS_MAX_FT}
    )
    return bool(has_frontage)


async def _market_has_streets(session: AsyncSession, parcel_number: str) -> bool:
    exists = await session.scalar(_MARKET_STREETS_SQL, {"parcel_number": parcel_number})
    return bool(exists)


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
    street_data = await _market_has_streets(session, parcel_number) if parcel.has_geometry else True
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
            access=AccessSignal(
                has_geometry=parcel.has_geometry,
                has_street_frontage=has_frontage,
                street_data_available=street_data,
            ),
            historic=historic,
            overlays=overlays,
            rco=rco,
        )
    )
    return RiskResult(
        parcel_number=parcel_number,
        risk_score=assessment.risk_score,
        flags=[_flag_schema(flag) for flag in assessment.flags],
        summary=assessment.summary,
        confidence=assessment.confidence,
        sources=[{"source": source} for source in _CHECKED_SOURCES],
        computed_at=computed_at,
    )


_SHERIFF_SELECT = (
    "SELECT ss.parcel_number, p.address, ss.case_number, ss.sale_type, ss.sale_date, "
    "ss.status, ss.opening_bid, ss.plaintiff, "
    "p.is_vacant, p.base_zoning_code, p.lot_area_sqft, pv.max_allowable_offer, "
    "(pv.max_allowable_offer - ss.opening_bid) AS bid_gap, "
    "round(pv.opportunity_score)::int AS opportunity_score "
    "FROM sheriff_sale ss "
    "JOIN parcel p ON p.parcel_number = ss.parcel_number "
    "LEFT JOIN parcel_screen pv ON pv.parcel_number = ss.parcel_number"
)


async def list_sheriff_sales(
    session: AsyncSession,
    *,
    market_code: str = "phl",
    date_from: date | None = None,
    date_to: date | None = None,
    zip_code: str | None = None,
    limit: int = 200,
) -> SheriffSaleCalendar:
    conditions: list[str] = ["p.market_code = :market_code"]
    params: dict[str, Any] = {"limit": limit, "market_code": market_code}
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
            is_vacant=row.is_vacant,
            base_zoning_code=row.base_zoning_code,
            lot_area_sqft=_as_float(row.lot_area_sqft),
            max_allowable_offer=_as_float(row.max_allowable_offer),
            bid_gap=_as_float(row.bid_gap),
            opportunity_score=row.opportunity_score,
        )
        for row in rows
    ]
    has_upcoming = any(item.sale_date is not None for item in items)
    return SheriffSaleCalendar(
        market=market_code,
        label=SHERIFF_SALE_SURFACE_LABEL,
        state="live" if has_upcoming else "empty",
        note=None if has_upcoming else _NO_UPCOMING_SALES_NOTE,
        total=int(total or 0),
        returned=len(items),
        items=items,
    )


def _ics_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def sheriff_sale_ics(calendar: SheriffSaleCalendar, *, now: datetime) -> str:
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//LotScope//Sales Calendar//EN",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{_ics_escape(calendar.label)}",
    ]
    for item in calendar.items:
        if item.sale_date is None:
            continue
        where = item.address or item.parcel_number
        summary = f"{calendar.label}: {where}"
        detail_parts = [f"Case {item.case_number}"]
        if item.opening_bid is not None:
            detail_parts.append(f"Opening bid ${round(item.opening_bid):,}")
        if item.max_allowable_offer is not None:
            detail_parts.append(f"Max allowable offer ${round(item.max_allowable_offer):,}")
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{_ics_escape(item.case_number)}@parcelphl.online",
                f"DTSTAMP:{stamp}",
                f"DTSTART;VALUE=DATE:{item.sale_date.strftime('%Y%m%d')}",
                f"SUMMARY:{_ics_escape(summary)}",
                f"DESCRIPTION:{_ics_escape('. '.join(detail_parts))}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


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


_SHERIFF_DATES_SQL = text(
    "SELECT ss.sale_date, count(*) AS listings, "
    "       count(*) FILTER (WHERE coalesce(p.is_vacant, false)) AS vacant "
    "FROM sheriff_sale ss "
    "JOIN parcel p ON p.parcel_number = ss.parcel_number "
    "WHERE p.market_code = :market_code "
    "  AND ss.sale_date >= current_date "
    "  AND coalesce(ss.status, '') <> ALL(:not_scheduled_statuses) "
    "GROUP BY ss.sale_date ORDER BY ss.sale_date"
)


async def list_sheriff_sale_dates(
    session: AsyncSession, *, market_code: str = MARKET_CODE
) -> SheriffSaleDates:
    rows = (
        await session.execute(
            _SHERIFF_DATES_SQL,
            {
                "market_code": market_code,
                "not_scheduled_statuses": list(NOT_SCHEDULED_STATUSES),
            },
        )
    ).all()
    return SheriffSaleDates(
        market=market_code,
        dates=[
            SheriffSaleDate(
                sale_date=row.sale_date, listings=int(row.listings), vacant=int(row.vacant)
            )
            for row in rows
        ],
        computed_at=datetime.now(UTC),
    )


RECENT_CHANGE_DAYS = 14

_RECENT_CHANGES_SQL = text(
    "SELECT parcel_number, sale_date, old_status, new_status, old_sale_date, new_sale_date, "
    "observed_at FROM sheriff_sale_event "
    "WHERE parcel_number = :parcel_number "
    "AND observed_at >= now() - make_interval(days => :days) "
    "ORDER BY observed_at DESC"
)


def _change_summary(row: Any) -> str:
    if row.new_sale_date is not None and row.old_sale_date != row.new_sale_date:
        moved = row.new_sale_date.strftime("%b %-d")
        return f"continued to {moved}"
    if row.new_status and row.new_status != row.old_status:
        return str(row.new_status).lower()
    return "changed"


async def recent_sheriff_changes(
    session: AsyncSession, parcel_number: str, *, days: int = RECENT_CHANGE_DAYS
) -> list[SheriffSaleChange]:
    rows = (
        await session.execute(_RECENT_CHANGES_SQL, {"parcel_number": parcel_number, "days": days})
    ).all()
    return [
        SheriffSaleChange(
            parcel_number=row.parcel_number,
            sale_date=row.sale_date,
            old_status=row.old_status,
            new_status=row.new_status,
            old_sale_date=row.old_sale_date,
            new_sale_date=row.new_sale_date,
            observed_at=row.observed_at,
            summary=_change_summary(row),
        )
        for row in rows
    ]
