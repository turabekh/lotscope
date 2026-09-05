"""Build one night's signals for one buyer.

Every signal is derived from a row that already exists: a sheriff event, a deed, a violation,
a filing. Nothing here invents a finding — it selects rows the buyer has a reason to care
about and records which row each one came from, so a line in the brief can always be traced
back to the record behind it.

Idempotent on (user_id, signal_key): running the job twice, or re-running it after a failure,
produces the same rows rather than a second brief's worth of duplicates.
"""

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.agent.alerts import AgentAlert
from lotscope.agent.signals import AnalystSignal
from lotscope.agent.tools import urls
from lotscope.agent.watch_spec import WatchSpec, spec_conditions
from lotscope.buybox.schemas import BuyBoxRead
from lotscope.core.market import MARKET_CODE

LOOKBACK_HOURS = 26
ADJACENCY_TOLERANCE_FT = 3.0
MAX_SIGNALS_PER_KIND = 25


@dataclass(frozen=True)
class Scope:
    """The parcels one buyer has a reason to hear about."""

    followed: tuple[str, ...]  # packets, pipeline, watchlist, owned
    owned: tuple[str, ...]
    areas: tuple[dict[str, Any], ...]


_FOLLOWED_SQL = text(
    "SELECT DISTINCT parcel_number FROM ("
    "  SELECT parcel_number FROM deal WHERE user_id = :u"
    "  UNION SELECT parcel_number FROM saved_parcel WHERE user_id = :u"
    "  UNION SELECT jsonb_array_elements("
    "    coalesce(model_json->'lots', '[]'::jsonb)"
    "  )->>'parcel_number' AS parcel_number FROM sale_packet WHERE user_id = :u"
    "    AND sale_date >= current_date - 30"
    ") s WHERE parcel_number IS NOT NULL"
)

_ADJACENT_SQL = text(
    "SELECT DISTINCT n.parcel_number FROM parcel t "
    "JOIN parcel n ON n.parcel_number <> t.parcel_number "
    "  AND n.market_code = t.market_code AND n.geom_local IS NOT NULL "
    "  AND ST_DWithin(n.geom_local, t.geom_local, :tolerance) "
    "WHERE t.parcel_number = ANY(:owned) AND t.geom_local IS NOT NULL"
)


def area_clause(areas: tuple[dict[str, Any], ...], alias: str) -> tuple[str, dict[str, Any]]:
    """A WHERE fragment for the buyer's areas. No areas means the whole city, not nothing."""
    if not areas:
        return "TRUE", {}
    clauses: list[str] = []
    params: dict[str, Any] = {}
    for index, area in enumerate(areas):
        polygon = area.get("polygon")
        zips = [str(code).strip() for code in area.get("zip_codes") or [] if str(code).strip()]
        if polygon:
            params[f"poly_{index}"] = json.dumps(polygon)
            clauses.append(
                f"ST_Intersects({alias}.geom_4326, "
                f"ST_SetSRID(ST_GeomFromGeoJSON(:poly_{index}), 4326))"
            )
        elif zips:
            params[f"zips_{index}"] = zips
            clauses.append(f"left({alias}.zip_code, 5) = ANY(:zips_{index})")
    if not clauses:
        return "TRUE", {}
    return "(" + " OR ".join(clauses) + ")", params


async def read_scope(session: AsyncSession, user_id: int, buy_box: BuyBoxRead) -> Scope:
    followed = set((await session.execute(_FOLLOWED_SQL, {"u": user_id})).scalars().all())
    owned = tuple(buy_box.owned_parcels)
    followed.update(owned)
    return Scope(
        followed=tuple(sorted(followed)),
        owned=owned,
        areas=tuple(area.model_dump() for area in buy_box.areas),
    )


async def adjacent_parcels(session: AsyncSession, owned: tuple[str, ...]) -> list[str]:
    if not owned:
        return []
    rows = await session.execute(
        _ADJACENT_SQL, {"owned": list(owned), "tolerance": ADJACENCY_TOLERANCE_FT}
    )
    return list(rows.scalars())


def _signal(
    *,
    user_id: int,
    on_date: date,
    kind: str,
    parcel_number: str | None,
    headline: str,
    detail: dict[str, Any],
    source: str,
    source_url: str | None,
    source_table: str,
    source_row_id: str | int,
    observed_at: datetime | None,
) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "signal_key": f"{kind}:{source_table}:{source_row_id}",
        "signal_date": on_date,
        "kind": kind,
        "parcel_number": parcel_number,
        "headline": headline,
        "detail": detail,
        "source": source,
        "source_url": source_url,
        "source_table": source_table,
        "source_row_id": str(source_row_id),
        "observed_at": observed_at,
    }


async def _sale_status(
    session: AsyncSession, user_id: int, scope: Scope, since: datetime, on_date: date
) -> list[dict[str, Any]]:
    if not scope.followed:
        return []
    rows = (
        (
            await session.execute(
                text(
                    "SELECT e.id, e.parcel_number, e.case_number, e.old_status, e.new_status, "
                    "e.old_sale_date, e.new_sale_date, e.observed_at, p.address "
                    "FROM sheriff_sale_event e LEFT JOIN parcel p USING (parcel_number) "
                    "WHERE e.observed_at >= :since AND e.parcel_number = ANY(:parcels) "
                    "ORDER BY e.observed_at DESC LIMIT :limit"
                ),
                {"since": since, "parcels": list(scope.followed), "limit": MAX_SIGNALS_PER_KIND},
            )
        )
        .mappings()
        .all()
    )
    signals = []
    for row in rows:
        moved = row["old_sale_date"] != row["new_sale_date"]
        what = (
            f"sale date moved {row['old_sale_date']} → {row['new_sale_date']}"
            if moved
            else f"status {row['old_status'] or 'unknown'} → {row['new_status'] or 'unknown'}"
        )
        signals.append(
            _signal(
                user_id=user_id,
                on_date=on_date,
                kind="sale_status",
                parcel_number=row["parcel_number"],
                headline=f"{row['address'] or row['parcel_number']}: {what}",
                detail={
                    "case_number": row["case_number"],
                    "old_status": row["old_status"],
                    "new_status": row["new_status"],
                    "old_sale_date": str(row["old_sale_date"] or ""),
                    "new_sale_date": str(row["new_sale_date"] or ""),
                },
                source="civilview",
                source_url=urls.CIVILVIEW,
                source_table="sheriff_sale_event",
                source_row_id=row["id"],
                observed_at=row["observed_at"],
            )
        )
    return signals


async def _neighbor_delinquency(
    session: AsyncSession, user_id: int, neighbors: list[str], since: datetime, on_date: date
) -> list[dict[str, Any]]:
    if not neighbors:
        return []
    rows = (
        (
            await session.execute(
                text(
                    "SELECT t.parcel_number, t.total_due, t.delinquency_owner, t.updated_at, "
                    "p.address FROM tax_status t LEFT JOIN parcel p USING (parcel_number) "
                    "WHERE t.parcel_number = ANY(:parcels) AND t.is_delinquent IS TRUE "
                    "AND t.updated_at >= :since ORDER BY t.total_due DESC NULLS LAST "
                    "LIMIT :limit"
                ),
                {"parcels": neighbors, "since": since, "limit": MAX_SIGNALS_PER_KIND},
            )
        )
        .mappings()
        .all()
    )
    return [
        _signal(
            user_id=user_id,
            on_date=on_date,
            kind="neighbor_delinquency",
            parcel_number=row["parcel_number"],
            headline=(
                f"Next door to a lot you own — {row['address'] or row['parcel_number']} is "
                f"delinquent, ${float(row['total_due'] or 0):,.0f} owed"
            ),
            detail={
                "total_due": float(row["total_due"]) if row["total_due"] is not None else None,
                "debtor": row["delinquency_owner"],
            },
            source="tax_delinquency",
            source_url=urls.TAX_URL,
            source_table="tax_status",
            source_row_id=row["parcel_number"],
            observed_at=row["updated_at"],
        )
        for row in rows
    ]


async def _neighbor_violation(
    session: AsyncSession, user_id: int, neighbors: list[str], since: datetime, on_date: date
) -> list[dict[str, Any]]:
    if not neighbors:
        return []
    rows = (
        (
            await session.execute(
                text(
                    "SELECT e.id, e.parcel_number, e.description, e.event_date, e.created_at, "
                    "e.is_unsafe, p.address FROM li_event e LEFT JOIN parcel p USING "
                    "(parcel_number) WHERE e.parcel_number = ANY(:parcels) "
                    "AND e.event_type = 'violation' AND e.created_at >= :since "
                    "ORDER BY e.created_at DESC LIMIT :limit"
                ),
                {"parcels": neighbors, "since": since, "limit": MAX_SIGNALS_PER_KIND},
            )
        )
        .mappings()
        .all()
    )
    return [
        _signal(
            user_id=user_id,
            on_date=on_date,
            kind="neighbor_violation",
            parcel_number=row["parcel_number"],
            headline=(
                f"New violation next door to a lot you own — "
                f"{row['address'] or row['parcel_number']}: "
                f"{(row['description'] or 'violation').strip()[:90]}"
            ),
            detail={
                "violation_date": str(row["event_date"] or ""),
                "unsafe": bool(row["is_unsafe"]),
            },
            source="li_violations",
            source_url=urls.li_history(row["address"]),
            source_table="li_event",
            source_row_id=row["id"],
            observed_at=row["created_at"],
        )
        for row in rows
    ]


async def _neighbor_deed(
    session: AsyncSession, user_id: int, neighbors: list[str], since: datetime, on_date: date
) -> list[dict[str, Any]]:
    if not neighbors:
        return []
    rows = (
        (
            await session.execute(
                text(
                    "SELECT s.id, s.parcel_number, s.grantee, s.sale_price, s.sale_date, "
                    "s.created_at, p.address FROM sale s LEFT JOIN parcel p USING "
                    "(parcel_number) WHERE s.parcel_number = ANY(:parcels) "
                    "AND s.created_at >= :since ORDER BY s.sale_date DESC NULLS LAST "
                    "LIMIT :limit"
                ),
                {"parcels": neighbors, "since": since, "limit": MAX_SIGNALS_PER_KIND},
            )
        )
        .mappings()
        .all()
    )
    return [
        _signal(
            user_id=user_id,
            on_date=on_date,
            kind="neighbor_deed",
            parcel_number=row["parcel_number"],
            headline=(
                f"A lot next to yours changed hands — "
                f"{row['address'] or row['parcel_number']} to "
                f"{(row['grantee'] or 'an unnamed grantee')[:60]}"
                + (
                    f" for ${float(row['sale_price']):,.0f}"
                    if row["sale_price"] is not None
                    else ""
                )
            ),
            detail={
                "grantee": row["grantee"],
                "sale_date": str(row["sale_date"] or ""),
                "sale_price": float(row["sale_price"]) if row["sale_price"] is not None else None,
            },
            source="rtt_summary",
            source_url=urls.RTT_URL,
            source_table="sale",
            source_row_id=row["id"],
            observed_at=row["created_at"],
        )
        for row in rows
    ]


async def _zba_filing(
    session: AsyncSession, user_id: int, scope: Scope, since: datetime, on_date: date
) -> list[dict[str, Any]]:
    clause, params = area_clause(scope.areas, "p")
    rows = (
        (
            await session.execute(
                text(
                    "SELECT z.id, z.appeal_number, z.parcel_number, z.appeal_type, "
                    "z.decision, z.address, z.created_at FROM zba_appeal z "
                    "JOIN parcel p USING (parcel_number) "
                    f"WHERE z.created_at >= :since AND p.market_code = :m AND {clause} "
                    "ORDER BY z.created_at DESC LIMIT :limit"
                ),
                {"since": since, "m": MARKET_CODE, "limit": MAX_SIGNALS_PER_KIND, **params},
            )
        )
        .mappings()
        .all()
    )
    return [
        _signal(
            user_id=user_id,
            on_date=on_date,
            kind="zba_filing",
            parcel_number=row["parcel_number"],
            headline=(
                f"Zoning appeal filed in your area — "
                f"{row['address'] or row['parcel_number']}: "
                f"{row['appeal_type'] or 'appeal'} ({row['decision'] or 'undecided'})"
            ),
            detail={"appeal_number": row["appeal_number"], "decision": row["decision"]},
            source="zba_appeals",
            source_url=urls.ZONING_URL,
            source_table="zba_appeal",
            source_row_id=row["id"],
            observed_at=row["created_at"],
        )
        for row in rows
    ]


async def _new_listing(
    session: AsyncSession,
    user_id: int,
    since: datetime,
    on_date: date,
    *,
    area_sql: str,
    area_params: dict[str, Any],
    spec: WatchSpec,
    label: str,
    alert_id: int | None = None,
) -> list[dict[str, Any]]:
    """New sheriff listings that match one standing description.

    The same query serves the buy box and a watched search: both are an area plus filters.
    The full grade is what a packet is for, so the headline says "worth a look", never a
    grade — a brief must not imply a screen that was never run.
    """
    conditions, params = spec_conditions(spec, "p")
    params.update(area_params)

    rows = (
        (
            await session.execute(
                text(
                    "SELECT s.id, s.parcel_number, s.case_number, s.sale_date, s.opening_bid, "
                    "s.created_at, p.address, p.lot_area_sqft FROM sheriff_sale s "
                    "JOIN parcel p USING (parcel_number) "
                    f"WHERE s.created_at >= :since AND p.market_code = :m "
                    f"AND {area_sql} AND {' AND '.join(conditions)} "
                    "ORDER BY s.sale_date LIMIT :limit"
                ),
                {"since": since, "m": MARKET_CODE, "limit": MAX_SIGNALS_PER_KIND, **params},
            )
        )
        .mappings()
        .all()
    )
    return [
        _signal(
            user_id=user_id,
            on_date=on_date,
            kind="new_listing",
            parcel_number=row["parcel_number"],
            headline=(
                f"New sheriff listing {label} worth a look — "
                f"{row['address'] or row['parcel_number']}, sale {row['sale_date']}"
            ),
            detail={
                "case_number": row["case_number"],
                "sale_date": str(row["sale_date"] or ""),
                "opening_bid": float(row["opening_bid"])
                if row["opening_bid"] is not None
                else None,
                "lot_area_sqft": float(row["lot_area_sqft"])
                if row["lot_area_sqft"] is not None
                else None,
                "matched": label,
                "screened": False,
                **({"alert_id": alert_id} if alert_id is not None else {}),
            },
            source="civilview",
            source_url=urls.CIVILVIEW,
            source_table="sheriff_sale",
            source_row_id=row["id"],
            observed_at=row["created_at"],
        )
        for row in rows
    ]


def buy_box_spec(buy_box: BuyBoxRead) -> WatchSpec:
    """The buy box, expressed as the same standing description a watch uses."""
    return WatchSpec(
        name="your buy box",
        zoning_codes=list(buy_box.zoning_codes),
        vacant_only=True,
        exclude_city_owned=buy_box.exclude_city_neighbor,
        min_lot_area_sqft=float(buy_box.min_lot_sqft) if buy_box.min_lot_sqft else None,
    )


_ALERT_KIND_TO_SIGNAL = {
    "sale_status": "sale_status",
    "new_violation": "neighbor_violation",
    "new_delinquency": "neighbor_delinquency",
    "neighbor_deed": "neighbor_deed",
    "zba_filing": "zba_filing",
    "new_match": "new_listing",
}


async def _alert_parcels(
    session: AsyncSession, alert: AgentAlert, scope: Scope, neighbors: list[str]
) -> list[str]:
    if alert.scope == "parcel":
        target = alert.target.get("parcel_number") or alert.target.get("parcel")
        return [str(target)] if target else []
    if alert.scope == "owned_neighbors":
        return neighbors
    clause, params = area_clause(scope.areas, "p")
    rows = await session.execute(
        text(f"SELECT parcel_number FROM parcel p WHERE p.market_code = :m AND {clause} LIMIT 500"),
        {"m": MARKET_CODE, **params},
    )
    return list(rows.scalars())


async def build_signals(
    session: AsyncSession,
    *,
    user_id: int,
    buy_box: BuyBoxRead,
    on_date: date | None = None,
    since: datetime | None = None,
) -> list[AnalystSignal]:
    on_date = on_date or datetime.now(UTC).date()
    since = since or (datetime.now(UTC) - timedelta(hours=LOOKBACK_HOURS))

    scope = await read_scope(session, user_id, buy_box)
    neighbors = await adjacent_parcels(session, scope.owned)

    rows: list[dict[str, Any]] = []
    rows += await _sale_status(session, user_id, scope, since, on_date)
    rows += await _neighbor_delinquency(session, user_id, neighbors, since, on_date)
    rows += await _neighbor_violation(session, user_id, neighbors, since, on_date)
    rows += await _neighbor_deed(session, user_id, neighbors, since, on_date)
    rows += await _zba_filing(session, user_id, scope, since, on_date)
    area_sql, area_params = area_clause(scope.areas, "p")
    rows += await _new_listing(
        session,
        user_id,
        since,
        on_date,
        area_sql=area_sql,
        area_params=area_params,
        spec=buy_box_spec(buy_box),
        label="in your area",
    )

    # Anything the buyer explicitly asked to be alerted about, over its own scope.
    alerts = (
        (
            await session.execute(
                select(AgentAlert).where(
                    AgentAlert.user_id == user_id, AgentAlert.is_active.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )
    for alert in alerts:
        signal_kind = _ALERT_KIND_TO_SIGNAL.get(alert.kind)
        if signal_kind is None:
            continue
        parcels = await _alert_parcels(session, alert, scope, neighbors)
        if not parcels and signal_kind != "new_listing":
            continue
        alert_scope = Scope(followed=tuple(parcels), owned=scope.owned, areas=scope.areas)
        if signal_kind == "sale_status":
            found = await _sale_status(session, user_id, alert_scope, since, on_date)
        elif signal_kind == "neighbor_violation":
            found = await _neighbor_violation(session, user_id, parcels, since, on_date)
        elif signal_kind == "neighbor_delinquency":
            found = await _neighbor_delinquency(session, user_id, parcels, since, on_date)
        elif signal_kind == "neighbor_deed":
            found = await _neighbor_deed(session, user_id, parcels, since, on_date)
        elif signal_kind == "new_listing":
            spec = WatchSpec.model_validate(alert.target or {})
            watched_sql, watched_params = area_clause(scope.areas, "p")
            found = await _new_listing(
                session,
                user_id,
                since,
                on_date,
                # A watched spec carries its own zips; the buyer's areas do not narrow it.
                area_sql="TRUE" if spec.zip_codes else watched_sql,
                area_params={} if spec.zip_codes else watched_params,
                spec=spec,
                label=f"matching “{spec.name}”",
                alert_id=alert.id,
            )
        else:
            found = await _zba_filing(session, user_id, alert_scope, since, on_date)
        for row in found:
            row["detail"] = {**row["detail"], "alert_id": alert.id}
        rows += found

    if not rows:
        return []

    # Last write wins per key within this batch, so an alert's copy of a row does not
    # collide with the default one.
    unique = {row["signal_key"]: row for row in rows}
    statement = (
        insert(AnalystSignal)
        .values(list(unique.values()))
        .on_conflict_do_nothing(constraint="uq_analyst_signal_user_key")
        .returning(AnalystSignal)
    )
    inserted = (await session.execute(statement)).scalars().all()
    return list(inserted)
