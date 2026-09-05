from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.buybox.service import buy_box_assumptions, read_buy_box
from lotscope.core.config import get_settings
from lotscope.core.errors import NotFoundError, ValidationError
from lotscope.core.market import MARKET_CODE
from lotscope.packet.compose import (
    LI_URL,
    OPA_URL,
    RTT_URL,
    SHERIFF_URL,
    TAX_URL,
    ZONING_URL,
    LotInputs,
    compose_packet,
)
from lotscope.packet.models import SalePacket
from lotscope.packet.render import packet_filename, render_packet_pdf
from lotscope.packet.schemas import DataAsOf, PacketComp, PacketModel
from lotscope.risk.service import NOT_SCHEDULED_STATUSES
from lotscope.underwriting.matching import required_margin

MAX_COMPS_PER_LOT = 3

_LISTINGS_SQL = text(
    "SELECT DISTINCT ON (ss.parcel_number) ss.parcel_number, ss.case_number, ss.sale_type, "
    "ss.sale_date, ss.status, ss.opening_bid, ss.plaintiff, "
    "p.address, p.is_vacant, p.lot_area_sqft, p.base_zoning_code, p.geom_local "
    "FROM sheriff_sale ss JOIN parcel p USING (parcel_number) "
    "WHERE ss.sale_date = :sale_date AND p.market_code = :market_code "
    "AND coalesce(ss.status, '') <> ALL(:not_scheduled_statuses) "
    "ORDER BY ss.parcel_number, ss.updated_at DESC"
)

_VERDICT_SQL = text(
    "SELECT parcel_number, can_build_by_right, by_right_units, max_allowable_offer, est_margin "
    "FROM parcel_verdict WHERE parcel_number = ANY(:parcels)"
)

_VIOLATIONS_SQL = text(
    "SELECT parcel_number, count(*) AS open_count, max(event_date) AS most_recent, "
    "bool_or(coalesce(is_unsafe, false) OR coalesce(is_imminently_dangerous, false)) AS unsafe "
    "FROM li_event WHERE parcel_number = ANY(:parcels) "
    "AND event_type = 'violation' AND coalesce(case_status, status, '') NOT ILIKE '%closed%' "
    "GROUP BY parcel_number"
)

_TAX_SQL = text(
    "SELECT parcel_number, is_delinquent, total_due, delinquency_owner "
    "FROM tax_status WHERE parcel_number = ANY(:parcels)"
)

_OVERLAY_SQL = text(
    "SELECT parcel_number, overlay_code FROM parcel_overlay WHERE parcel_number = ANY(:parcels)"
)

_HISTORIC_SQL = text(
    "SELECT p.parcel_number FROM parcel p JOIN historic_district h "
    "ON ST_Intersects(h.geom_local, p.geom_local) WHERE p.parcel_number = ANY(:parcels)"
)

_FLOOD_SQL = text(
    "SELECT DISTINCT p.parcel_number FROM parcel p JOIN flood_zone f "
    "ON ST_Intersects(f.geom_local, p.geom_local) "
    "WHERE p.parcel_number = ANY(:parcels) "
    "AND (upper(f.zone) LIKE 'A%' OR upper(f.zone) LIKE 'V%')"
)

_CITY_NEIGHBOUR_SQL = text(
    "SELECT DISTINCT p.parcel_number FROM parcel p JOIN parcel n "
    "ON n.parcel_number <> p.parcel_number AND ST_DWithin(n.geom_local, p.geom_local, 10) "
    "WHERE p.parcel_number = ANY(:parcels) AND n.owner_key ~ "
    "'(CITY OF PHILA|PHILADELPHIA HOUSING|REDEVELOPMENT AUTH|LAND BANK|PHDC)'"
)

_COMPS_SQL = text(
    "SELECT subject.parcel_number AS subject, c.parcel_number, c.address, "
    "s.sale_date, s.sale_price, "
    "ST_Distance(c.geom_local, subject.geom_local) AS distance_ft "
    "FROM parcel subject "
    "JOIN parcel c ON c.parcel_number <> subject.parcel_number "
    "AND ST_DWithin(c.geom_local, subject.geom_local, :radius_ft) "
    "JOIN sale s ON s.parcel_number = c.parcel_number "
    "WHERE subject.parcel_number = ANY(:parcels) "
    "AND s.sale_price >= :min_price "
    "AND s.sale_date >= current_date - make_interval(years => :years) "
    "ORDER BY subject.parcel_number, ST_Distance(c.geom_local, subject.geom_local)"
)

_FRESHNESS_SQL = text(
    "SELECT dataset, last_success_at, data_vintage FROM dataset_freshness "
    "WHERE market_code = :market_code AND dataset = ANY(:datasets)"
)

_DATASET_URLS = {
    "opa_properties_public": OPA_URL,
    "rtt_summary": RTT_URL,
    "violations": LI_URL,
    "real_estate_tax_delinquencies": TAX_URL,
    "zoning_base_districts": ZONING_URL,
    "sheriff_sale": SHERIFF_URL,
}

_SOURCE_FOR_DATASET = {
    "opa_properties_public": "parcel",
    "rtt_summary": "rtt_summary",
    "violations": "li_event",
    "real_estate_tax_delinquencies": "tax_status",
    "zoning_base_districts": "zoning_overlays",
    "sheriff_sale": "sheriff_sale",
}


async def _rows(session: AsyncSession, statement: Any, params: dict[str, Any]) -> list[Any]:
    return list((await session.execute(statement, params)).mappings())


async def build_packet_model(session: AsyncSession, user_id: int, sale_date: date) -> PacketModel:
    listings = await _rows(
        session,
        _LISTINGS_SQL,
        {
            "sale_date": sale_date,
            "market_code": MARKET_CODE,
            "not_scheduled_statuses": list(NOT_SCHEDULED_STATUSES),
        },
    )
    if not listings:
        raise NotFoundError(f"No sheriff-sale listings are recorded for {sale_date.isoformat()}.")

    parcels = [row["parcel_number"] for row in listings]
    keyed = {"parcels": parcels}

    verdicts = {row["parcel_number"]: row for row in await _rows(session, _VERDICT_SQL, keyed)}
    violations = {row["parcel_number"]: row for row in await _rows(session, _VIOLATIONS_SQL, keyed)}
    taxes = {row["parcel_number"]: row for row in await _rows(session, _TAX_SQL, keyed)}
    historic = {row["parcel_number"] for row in await _rows(session, _HISTORIC_SQL, keyed)}
    flood = {row["parcel_number"] for row in await _rows(session, _FLOOD_SQL, keyed)}
    city = {row["parcel_number"] for row in await _rows(session, _CITY_NEIGHBOUR_SQL, keyed)}

    overlays: dict[str, list[str]] = defaultdict(list)
    for row in await _rows(session, _OVERLAY_SQL, keyed):
        overlays[row["parcel_number"]].append(row["overlay_code"])

    comps: dict[str, list[PacketComp]] = defaultdict(list)
    for row in await _rows(
        session,
        _COMPS_SQL,
        {**keyed, "radius_ft": 1500.0, "min_price": 10_000.0, "years": 3},
    ):
        bucket = comps[row["subject"]]
        if len(bucket) >= MAX_COMPS_PER_LOT:
            continue
        bucket.append(
            PacketComp(
                parcel_number=row["parcel_number"],
                address=row["address"],
                sale_date=row["sale_date"],
                sale_price=float(row["sale_price"]),
                distance_ft=float(row["distance_ft"]),
                reason=(
                    f"Recorded sale {int(row['distance_ft'])} ft away"
                    f"{f' on {row["sale_date"].isoformat()}' if row['sale_date'] else ''}."
                ),
                source="rtt_summary",
                source_url=RTT_URL,
            )
        )

    freshness = {
        row["dataset"]: row
        for row in await _rows(
            session,
            _FRESHNESS_SQL,
            {"market_code": MARKET_CODE, "datasets": list(_DATASET_URLS)},
        )
    }
    fetched_by_source = {
        _SOURCE_FOR_DATASET[dataset]: row["last_success_at"]
        for dataset, row in freshness.items()
        if row["last_success_at"] is not None
    }
    fetched_by_source.setdefault("historicdistricts_local", None)
    data_as_of = [
        DataAsOf(
            source=dataset,
            source_url=_DATASET_URLS[dataset],
            fetched_at=row["last_success_at"],
            data_vintage=row["data_vintage"],
        )
        for dataset, row in sorted(freshness.items())
    ]

    lots: list[LotInputs] = []
    for row in listings:
        parcel = row["parcel_number"]
        verdict = verdicts.get(parcel)
        violation = violations.get(parcel)
        tax = taxes.get(parcel)
        lots.append(
            LotInputs(
                parcel_number=parcel,
                address=row["address"],
                case_number=row["case_number"],
                sale_type=row["sale_type"],
                sale_date=row["sale_date"],
                opening_bid=_as_float(row["opening_bid"]),
                status=row["status"],
                plaintiff=row["plaintiff"],
                is_vacant=bool(row["is_vacant"]),
                lot_area_sqft=_as_float(row["lot_area_sqft"]),
                zoning_code=row["base_zoning_code"],
                overlays=tuple(sorted(overlays.get(parcel, []))),
                can_build_by_right=verdict["can_build_by_right"] if verdict else None,
                by_right_units=verdict["by_right_units"] if verdict else None,
                max_allowable_offer=_as_float(verdict["max_allowable_offer"]) if verdict else None,
                est_margin=_as_float(verdict["est_margin"]) if verdict else None,
                open_violation_count=int(violation["open_count"]) if violation else 0,
                most_recent_violation=violation["most_recent"] if violation else None,
                has_unsafe_structure=bool(violation["unsafe"]) if violation else False,
                is_delinquent=bool(tax["is_delinquent"]) if tax else False,
                total_due=_as_float(tax["total_due"]) if tax else None,
                delinquency_owner=tax["delinquency_owner"] if tax else None,
                city_neighbor=parcel in city,
                in_historic_district=parcel in historic,
                in_flood_zone=parcel in flood,
                comps=tuple(comps.get(parcel, [])),
                sources_fetched_at={k: v for k, v in fetched_by_source.items() if v is not None},
            )
        )

    buy_box = await read_buy_box(session, user_id)
    assumptions = await buy_box_assumptions(session, user_id)
    margin = assumptions.get("target_margin", required_margin(buy_box))

    return compose_packet(
        sale_date=sale_date,
        buy_box=buy_box,
        required_margin=margin,
        lots=lots,
        data_as_of=data_as_of,
        generated_at=datetime.now(UTC),
    )


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


async def build_packet(session: AsyncSession, user_id: int, sale_date: date) -> SalePacket:
    packet = (
        await session.execute(
            select(SalePacket).where(
                SalePacket.user_id == user_id, SalePacket.sale_date == sale_date
            )
        )
    ).scalar_one_or_none()
    if packet is None:
        packet = SalePacket(user_id=user_id, sale_date=sale_date, status="pending")
        session.add(packet)
        await session.flush()

    try:
        model = await build_packet_model(session, user_id, sale_date)
        pdf = render_packet_pdf(model)
    except Exception as cause:
        packet.status = "failed"
        packet.error = str(cause)
        await session.flush()
        raise

    directory = Path(get_settings().packet_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / packet_filename(sale_date.isoformat(), user_id)
    path.write_bytes(pdf)

    packet.status = "ready"
    packet.error = None
    packet.pdf_path = str(path)
    packet.model_json = model.model_dump(mode="json")
    packet.generated_at = datetime.now(UTC)
    await session.flush()
    return packet


async def get_packet(session: AsyncSession, packet_id: int, user_id: int) -> SalePacket:
    packet = await session.get(SalePacket, packet_id)
    if packet is None or packet.user_id != user_id:
        raise NotFoundError(f"Packet {packet_id} was not found.")
    return packet


async def list_packets(session: AsyncSession, user_id: int) -> list[SalePacket]:
    return list(
        (
            await session.execute(
                select(SalePacket)
                .where(SalePacket.user_id == user_id)
                .order_by(SalePacket.sale_date.desc(), SalePacket.id.desc())
            )
        ).scalars()
    )


async def enqueue_packet(session: AsyncSession, user_id: int, sale_date: date) -> SalePacket:
    if sale_date < datetime.now(UTC).date():
        raise ValidationError("That sale date has already passed.")
    packet = (
        await session.execute(
            select(SalePacket).where(
                SalePacket.user_id == user_id, SalePacket.sale_date == sale_date
            )
        )
    ).scalar_one_or_none()
    if packet is None:
        packet = SalePacket(user_id=user_id, sale_date=sale_date, status="pending")
        session.add(packet)
    else:
        packet.status = "pending"
        packet.error = None
    await session.flush()
    return packet
