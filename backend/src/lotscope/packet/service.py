import re
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.buybox.service import buy_box_assumptions, read_buy_box
from lotscope.core.config import get_settings
from lotscope.core.errors import NotFoundError, ValidationError
from lotscope.core.logging import get_logger
from lotscope.core.market import MARKET_CODE
from lotscope.deal.analysis import DealAssumptions, DealInputs
from lotscope.deal.schemas import DealResult
from lotscope.deal.sensitivity import build_grid
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
from lotscope.packet.live_verify import verify_lots
from lotscope.packet.models import SalePacket
from lotscope.packet.render import packet_filename, render_packet_pdf
from lotscope.packet.schemas import AdjacentParcel, DataAsOf, PacketComp, PacketModel
from lotscope.risk.service import NOT_SCHEDULED_STATUSES
from lotscope.underwriting.matching import required_margin
from lotscope.valuation.service import sheriff_clearing_estimate
from lotscope.verdict.service import get_verdict_read
from lotscope.zba.schemas import VarianceOutlook
from lotscope.zba.service import variance_outlook
from lotscope.zoning.schemas import BuildabilityResult

_logger = get_logger(__name__)

MAX_COMPS_PER_LOT = 3
_FAVOURABLE_GRANT_RATE = 0.5

_LISTINGS_SQL = text(
    "SELECT DISTINCT ON (ss.parcel_number) ss.parcel_number, ss.case_number, ss.sale_type, "
    "ss.sale_date, ss.status, ss.opening_bid, ss.plaintiff, "
    "p.address, p.is_vacant, p.lot_area_sqft, p.base_zoning_code, p.geom_local "
    "FROM sheriff_sale ss JOIN parcel p USING (parcel_number) "
    "WHERE ss.sale_date = :sale_date AND p.market_code = :market_code "
    "AND coalesce(ss.status, '') <> ALL(:not_scheduled_statuses) "
    "ORDER BY ss.parcel_number, ss.updated_at DESC"
)


_ADJACENT_SQL = text(
    "SELECT t.parcel_number AS subject, n.parcel_number, n.address, n.lot_area_sqft, "
    "coalesce(n.is_city_owned, false) AS is_city_owned, coalesce(n.is_vacant, false) AS is_vacant, "
    "n.owner_key, "
    "ST_Length(ST_CollectionExtract(ST_Intersection(n.geom_local, t.geom_local), 2)) "
    "AS shared_boundary_ft "
    "FROM parcel t JOIN parcel n ON n.parcel_number <> t.parcel_number "
    "AND n.geom_local IS NOT NULL AND ST_Intersects(n.geom_local, t.geom_local) "
    "WHERE t.parcel_number = ANY(:parcels) AND t.geom_local IS NOT NULL "
    "AND n.market_code = :market_code "
    "ORDER BY t.parcel_number, shared_boundary_ft DESC NULLS LAST"
)

_PUBLIC_OWNER_PATTERN = "(CITY OF PHILA|PHILADELPHIA HOUSING|REDEVELOPMENT AUTH|LAND BANK|PHDC)"

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
    "AND c.is_vacant IS TRUE "
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


async def build_packet_model(
    session: AsyncSession, user_id: int, sale_date: date, *, redis: Redis | None = None
) -> PacketModel:
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

    violations = {row["parcel_number"]: row for row in await _rows(session, _VIOLATIONS_SQL, keyed)}
    taxes = {row["parcel_number"]: row for row in await _rows(session, _TAX_SQL, keyed)}
    historic = {row["parcel_number"] for row in await _rows(session, _HISTORIC_SQL, keyed)}
    flood = {row["parcel_number"] for row in await _rows(session, _FLOOD_SQL, keyed)}
    city = {row["parcel_number"] for row in await _rows(session, _CITY_NEIGHBOUR_SQL, keyed)}

    owned = {parcel.lower() for parcel in (await read_buy_box(session, user_id)).owned_parcels}
    adjacent: dict[str, list[AdjacentParcel]] = defaultdict(list)
    for row in await _rows(session, _ADJACENT_SQL, {**keyed, "market_code": MARKET_CODE}):
        owner_key = row["owner_key"] or ""
        if row["parcel_number"].lower() in owned:
            owner_class = "owned_by_you"
        elif row["is_city_owned"] or re.search(_PUBLIC_OWNER_PATTERN, owner_key):
            owner_class = "public"
        elif row["is_vacant"]:
            owner_class = "vacant"
        else:
            continue
        adjacent[row["subject"]].append(
            AdjacentParcel(
                parcel_number=row["parcel_number"],
                address=row["address"],
                owner_class=owner_class,
                shared_boundary_ft=_as_float(row["shared_boundary_ft"]),
                lot_area_sqft=_as_float(row["lot_area_sqft"]),
            )
        )

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

    buy_box = await read_buy_box(session, user_id)
    assumptions = await buy_box_assumptions(session, user_id)
    margin = assumptions.get("target_margin", required_margin(buy_box))
    computed_at = datetime.now(UTC)

    lots: list[LotInputs] = []
    for row in listings:
        parcel = row["parcel_number"]
        violation = violations.get(parcel)
        tax = taxes.get(parcel)
        vacant = bool(row["is_vacant"])

        buildability = None
        deal = None
        grid = None
        clearing = None
        variance_needed = None
        outlook_favourable = None
        outlook_basis = None
        if vacant:
            # One read, the same one the Lot page and the Analyst get, with this buyer's
            # own assumptions applied. The packet used to compose its own copy beside it.
            read = await get_verdict_read(session, parcel, redis=redis, user_id=user_id)
            buildability = read.buildability if read else None
            deal = read.deal if read else None
            if deal is not None:
                grid = build_grid(
                    DealInputs(
                        units=deal.units,
                        buildable_area_sqft=(
                            buildability.buildable_area_sqft if buildability else None
                        ),
                        estimated_floors=None,
                        finished_comp_prices=_comp_prices(comps.get(parcel, [])),
                        land_value=deal.acquisition_cost,
                        acquisition_price=None,
                    ),
                    _deal_assumptions(deal),
                    computed_at=computed_at,
                )
            clearing = await sheriff_clearing_estimate(session, parcel)
            if buildability is not None and buildability.can_build_by_right is not True:
                variance_needed = _variance_needed(buildability)
                outlook = await variance_outlook(session, parcel)
                outlook_favourable, outlook_basis = _outlook_read(outlook)

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
                is_vacant=vacant,
                lot_area_sqft=_as_float(row["lot_area_sqft"]),
                zoning_code=row["base_zoning_code"],
                overlays=tuple(sorted(overlays.get(parcel, []))),
                can_build_by_right=buildability.can_build_by_right if buildability else None,
                by_right_units=buildability.by_right_units if buildability else None,
                dimensional_reason=_dimensional_reason(buildability),
                provision_id=buildability.cited_section if buildability else None,
                max_allowable_offer=deal.max_allowable_offer if deal else None,
                est_margin=deal.margin if deal else None,
                sensitivity=grid,
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
                clearing_estimate=clearing.estimate if clearing else None,
                clearing_sample_size=clearing.sample_size if clearing else 0,
                clearing_low=clearing.low if clearing else None,
                clearing_high=clearing.high if clearing else None,
                clearing_sufficient=bool(clearing.sufficient) if clearing else False,
                clearing_reason=clearing.reason if clearing else None,
                clearing_source=clearing.source if clearing else None,
                clearing_source_url=clearing.source_url if clearing else None,
                adjacent=tuple(adjacent.get(parcel, [])),
                variance_needed=variance_needed,
                variance_outlook_favourable=outlook_favourable,
                variance_outlook_basis=outlook_basis,
                computed_at=computed_at,
                sources_fetched_at={k: v for k, v in fetched_by_source.items() if v is not None},
            )
        )

    return compose_packet(
        sale_date=sale_date,
        buy_box=buy_box,
        required_margin=margin,
        lots=lots,
        data_as_of=data_as_of,
        generated_at=computed_at,
    )


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def _comp_prices(entries: list[PacketComp]) -> list[float]:
    return [comp.sale_price for comp in entries if comp.sale_price is not None]


def _deal_assumptions(deal: DealResult) -> DealAssumptions:
    return DealAssumptions(
        construction_cost_per_sqft=deal.assumptions.construction_cost_per_sqft,
        soft_cost_pct=deal.assumptions.soft_cost_pct,
        selling_cost_pct=deal.assumptions.selling_cost_pct,
        target_margin=deal.assumptions.target_margin,
        default_unit_sqft=deal.assumptions.default_unit_sqft,
        max_unit_sqft=deal.assumptions.max_unit_sqft,
    )


def _dimensional_reason(buildability: BuildabilityResult | None) -> str | None:
    if buildability is None:
        return None
    for reason in buildability.reasons:
        if "minimum" in reason or "dimensional minimums" in reason:
            return reason
    return buildability.reasons[0] if buildability.reasons else None


def _variance_needed(buildability: BuildabilityResult) -> str | None:
    shortfalls = [reason for reason in buildability.reasons if "is below the" in reason]
    if not shortfalls:
        return None
    return " ".join(shortfalls)


def _outlook_read(outlook: VarianceOutlook | None) -> tuple[bool | None, str | None]:
    if outlook is None:
        return None, None
    rate = outlook.local_grant_rate if outlook.local_grant_rate is not None else outlook.grant_rate
    if rate is None:
        return None, outlook.reason
    scope = outlook.local_scope or outlook.population_label
    decided = outlook.local_decided if outlook.local_decided is not None else outlook.decided
    basis = (
        f"{rate:.0%} of {decided} decided appeals granted over {outlook.window_months} months "
        f"for {scope}"
    )
    return rate >= _FAVOURABLE_GRANT_RATE, basis


async def build_packet(
    session: AsyncSession,
    user_id: int,
    sale_date: date,
    *,
    redis: Redis | None = None,
    verify_live: bool = True,
) -> SalePacket:
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
        model = await build_packet_model(session, user_id, sale_date, redis=redis)
        if verify_live:
            # Only the lots worth bidding on. Verifying the PASS index would spend a
            # buyer's build time re-checking lots they have already been told to skip.
            disagreed = await verify_lots(session, model.lots, user_id=user_id, redis=redis)
            _logger.info(
                "packet_live_verified",
                sale_date=sale_date.isoformat(),
                lots=len(model.lots),
                disagreed=disagreed,
            )
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
