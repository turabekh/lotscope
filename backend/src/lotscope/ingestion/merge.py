from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.events import (
    TaxSnapshot,
    classify_li_event,
    diff_assessment,
    diff_tax,
    new_deed_event,
    sheriff_sale_event,
)
from lotscope.ingestion.models import ParcelEvent
from lotscope.risk.models import SheriffSaleEvent

TAX_DATASET = "tax_delinquency"
LI_DATASET = "li"
OPA_DATASET = "opa"
RTT_DATASET = "rtt"
SHERIFF_DATASET = "sheriff"

_STAGING_JOIN_SQL = text(
    "SELECT s.parcel_number, "
    "s.is_delinquent AS s_delinquent, s.total_due AS s_total_due, "
    "c.is_delinquent AS c_delinquent, c.total_due AS c_total_due, "
    "(c.parcel_number IS NOT NULL) AS has_core "
    "FROM staging.tax s "
    "LEFT JOIN tax_status c ON c.parcel_number = s.parcel_number "
    "WHERE s.ingest_run_id = :ingest_run_id"
)

_UPSERT_CORE_SQL = text(
    "INSERT INTO tax_status "
    "(parcel_number, is_delinquent, delinquency_owner, snapshot_period, total_due, "
    "principal_due, years_owed, updated_at) "
    "SELECT parcel_number, is_delinquent, delinquency_owner, snapshot_period, total_due, "
    "principal_due, years_owed, now() "
    "FROM staging.tax WHERE ingest_run_id = :ingest_run_id "
    "ON CONFLICT (parcel_number) DO UPDATE SET "
    "is_delinquent = excluded.is_delinquent, "
    "delinquency_owner = excluded.delinquency_owner, "
    "snapshot_period = excluded.snapshot_period, total_due = excluded.total_due, "
    "principal_due = excluded.principal_due, years_owed = excluded.years_owed, "
    "updated_at = now()"
)


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


@dataclass(frozen=True)
class MergeResult:
    merged_rows: int
    event_count: int


async def merge_tax(session: AsyncSession, ingest_run_id: int) -> MergeResult:
    rows = (await session.execute(_STAGING_JOIN_SQL, {"ingest_run_id": ingest_run_id})).all()

    events = 0
    for row in rows:
        old = (
            TaxSnapshot(
                is_delinquent=row.c_delinquent,
                total_due=_as_float(row.c_total_due),
            )
            if row.has_core
            else None
        )
        new = TaxSnapshot(
            is_delinquent=row.s_delinquent,
            total_due=_as_float(row.s_total_due),
        )
        for draft in diff_tax(old, new):
            session.add(
                ParcelEvent(
                    parcel_number=row.parcel_number,
                    dataset=TAX_DATASET,
                    code=draft.code,
                    severity=draft.severity,
                    old_value=draft.old_value,
                    new_value=draft.new_value,
                    ingest_run_id=ingest_run_id,
                )
            )
            events += 1

    await session.flush()
    await session.execute(_UPSERT_CORE_SQL, {"ingest_run_id": ingest_run_id})
    return MergeResult(merged_rows=len(rows), event_count=events)


_LI_JOIN_SQL = text(
    "SELECT s.parcel_number, s.event_type, s.external_id, "
    "s.is_unsafe, s.is_imminently_dangerous, (c.id IS NOT NULL) AS row_exists "
    "FROM staging.li_event s "
    "LEFT JOIN li_event c ON c.event_type = s.event_type AND c.external_id = s.external_id "
    "WHERE s.ingest_run_id = :ingest_run_id"
)

_LI_TYPE_SEEN_SQL = text("SELECT EXISTS (SELECT 1 FROM li_event WHERE event_type = :event_type)")

_UPSERT_LI_SQL = text(
    "INSERT INTO li_event "
    "(parcel_number, external_id, event_type, status, case_status, event_date, description, "
    "is_unsafe, is_imminently_dangerous, source, created_at, updated_at) "
    "SELECT parcel_number, external_id, event_type, status, case_status, event_date, "
    "description, is_unsafe, is_imminently_dangerous, source, now(), now() "
    "FROM staging.li_event WHERE ingest_run_id = :ingest_run_id "
    "ON CONFLICT (event_type, external_id) DO UPDATE SET "
    "status = excluded.status, case_status = excluded.case_status, "
    "event_date = excluded.event_date, "
    "description = excluded.description, is_unsafe = excluded.is_unsafe, "
    "is_imminently_dangerous = excluded.is_imminently_dangerous, updated_at = now()"
)


async def merge_li(session: AsyncSession, ingest_run_id: int, event_type: str) -> MergeResult:
    type_seen = bool(await session.scalar(_LI_TYPE_SEEN_SQL, {"event_type": event_type}))
    rows = (await session.execute(_LI_JOIN_SQL, {"ingest_run_id": ingest_run_id})).all()

    events = 0
    if type_seen:
        for row in rows:
            if row.row_exists:
                continue
            draft = classify_li_event(row.event_type, row.is_unsafe, row.is_imminently_dangerous)
            if draft is None:
                continue
            session.add(
                ParcelEvent(
                    parcel_number=row.parcel_number,
                    dataset=LI_DATASET,
                    code=draft.code,
                    severity=draft.severity,
                    old_value=draft.old_value,
                    new_value={"event_type": row.event_type, "external_id": row.external_id},
                    ingest_run_id=ingest_run_id,
                )
            )
            events += 1
        await session.flush()

    await session.execute(_UPSERT_LI_SQL, {"ingest_run_id": ingest_run_id})
    return MergeResult(merged_rows=len(rows), event_count=events)


_OPA_JOIN_SQL = text(
    "SELECT s.parcel_number, s.market_value AS s_market_value, "
    "c.market_value AS c_market_value, (c.parcel_number IS NOT NULL) AS has_core "
    "FROM staging.opa s "
    "LEFT JOIN parcel c ON c.parcel_number = s.parcel_number "
    "WHERE s.ingest_run_id = :ingest_run_id"
)

_UPSERT_OPA_SQL = text(
    "INSERT INTO parcel "
    "(parcel_number, address, zip_code, owner, mailing_address, land_use, base_zoning_code, "
    "market_value, land_value, improvement_value, exempt_land, exempt_building, "
    "lot_area_sqft, lot_area_source, frontage_ft, depth_ft, source, updated_at) "
    "SELECT parcel_number, address, zip_code, owner, mailing_address, land_use, base_zoning_code, "
    "market_value, land_value, improvement_value, exempt_land, exempt_building, "
    "lot_area_sqft, 'extract', frontage_ft, depth_ft, :source, now() "
    "FROM staging.opa WHERE ingest_run_id = :ingest_run_id "
    "ON CONFLICT (parcel_number) DO UPDATE SET "
    "address = excluded.address, zip_code = excluded.zip_code, owner = excluded.owner, "
    "mailing_address = excluded.mailing_address, land_use = excluded.land_use, "
    "base_zoning_code = excluded.base_zoning_code, market_value = excluded.market_value, "
    "land_value = excluded.land_value, improvement_value = excluded.improvement_value, "
    "exempt_land = excluded.exempt_land, exempt_building = excluded.exempt_building, "
    "lot_area_sqft = excluded.lot_area_sqft, lot_area_source = excluded.lot_area_source, "
    "frontage_ft = excluded.frontage_ft, depth_ft = excluded.depth_ft, updated_at = now()"
)


async def merge_opa(session: AsyncSession, ingest_run_id: int, *, source: str) -> MergeResult:
    rows = (await session.execute(_OPA_JOIN_SQL, {"ingest_run_id": ingest_run_id})).all()

    events = 0
    for row in rows:
        old = _as_float(row.c_market_value) if row.has_core else None
        draft = diff_assessment(old, _as_float(row.s_market_value))
        if draft is None:
            continue
        session.add(
            ParcelEvent(
                parcel_number=row.parcel_number,
                dataset=OPA_DATASET,
                code=draft.code,
                severity=draft.severity,
                old_value=draft.old_value,
                new_value=draft.new_value,
                ingest_run_id=ingest_run_id,
            )
        )
        events += 1

    await session.flush()
    await session.execute(_UPSERT_OPA_SQL, {"ingest_run_id": ingest_run_id, "source": source})
    return MergeResult(merged_rows=len(rows), event_count=events)


_RTT_SEEN_SQL = text("SELECT EXISTS (SELECT 1 FROM sale)")

_RTT_JOIN_SQL = text(
    "SELECT s.parcel_number, s.document_id, s.sale_price, "
    "(c.id IS NOT NULL) AS row_exists "
    "FROM staging.rtt s "
    "LEFT JOIN sale c ON c.parcel_number = s.parcel_number AND c.document_id = s.document_id "
    "WHERE s.ingest_run_id = :ingest_run_id"
)

_UPSERT_RTT_SQL = text(
    "INSERT INTO sale "
    "(parcel_number, document_id, document_type, sale_date, sale_price, "
    "grantor, grantee, source, updated_at) "
    "SELECT parcel_number, document_id, document_type, sale_date, sale_price, "
    "grantor, grantee, source, now() "
    "FROM staging.rtt WHERE ingest_run_id = :ingest_run_id "
    "ON CONFLICT (parcel_number, document_id) DO UPDATE SET "
    "document_type = excluded.document_type, sale_date = excluded.sale_date, "
    "sale_price = excluded.sale_price, grantor = excluded.grantor, "
    "grantee = excluded.grantee, updated_at = now()"
)


async def merge_rtt(session: AsyncSession, ingest_run_id: int) -> MergeResult:
    dataset_seen = bool(await session.scalar(_RTT_SEEN_SQL))
    rows = (await session.execute(_RTT_JOIN_SQL, {"ingest_run_id": ingest_run_id})).all()

    events = 0
    if dataset_seen:
        for row in rows:
            if row.row_exists:
                continue
            draft = new_deed_event(row.document_id, _as_float(row.sale_price))
            session.add(
                ParcelEvent(
                    parcel_number=row.parcel_number,
                    dataset=RTT_DATASET,
                    code=draft.code,
                    severity=draft.severity,
                    old_value=draft.old_value,
                    new_value=draft.new_value,
                    ingest_run_id=ingest_run_id,
                )
            )
            events += 1
        await session.flush()

    await session.execute(_UPSERT_RTT_SQL, {"ingest_run_id": ingest_run_id})
    return MergeResult(merged_rows=len(rows), event_count=events)


_SHERIFF_SEEN_SQL = text("SELECT EXISTS (SELECT 1 FROM sheriff_sale)")

_SHERIFF_JOIN_SQL = text(
    "SELECT s.parcel_number, s.case_number, s.sale_type, s.sale_date, s.opening_bid, "
    "(c.id IS NOT NULL) AS row_exists "
    "FROM staging.sheriff_sale s "
    "LEFT JOIN sheriff_sale c ON c.case_number = s.case_number "
    "WHERE s.ingest_run_id = :ingest_run_id"
)

_SHERIFF_CHANGES_SQL = text(
    "SELECT s.parcel_number, s.case_number, "
    "       c.status AS old_status, s.status AS new_status, "
    "       c.sale_date AS old_sale_date, s.sale_date AS new_sale_date "
    "FROM staging.sheriff_sale s "
    "JOIN sheriff_sale c ON c.case_number = s.case_number "
    "WHERE s.ingest_run_id = :ingest_run_id "
    "  AND ("
    "    (s.status IS NOT NULL AND s.status IS DISTINCT FROM c.status) "
    "    OR (s.sale_date IS NOT NULL AND s.sale_date IS DISTINCT FROM c.sale_date)"
    "  )"
)

_UPSERT_SHERIFF_SQL = text(
    "INSERT INTO sheriff_sale "
    "(parcel_number, case_number, sale_type, sale_date, status, opening_bid, "
    "plaintiff, source, updated_at) "
    "SELECT parcel_number, case_number, sale_type, sale_date, status, opening_bid, "
    "plaintiff, source, now() "
    "FROM staging.sheriff_sale WHERE ingest_run_id = :ingest_run_id "
    "ON CONFLICT (case_number) DO UPDATE SET "
    "parcel_number = excluded.parcel_number, plaintiff = excluded.plaintiff, "
    "sale_type = COALESCE(excluded.sale_type, sheriff_sale.sale_type), "
    "sale_date = COALESCE(excluded.sale_date, sheriff_sale.sale_date), "
    "status = COALESCE(excluded.status, sheriff_sale.status), "
    "opening_bid = COALESCE(excluded.opening_bid, sheriff_sale.opening_bid), "
    "updated_at = now()"
)


async def merge_sheriff(session: AsyncSession, ingest_run_id: int) -> MergeResult:
    dataset_seen = bool(await session.scalar(_SHERIFF_SEEN_SQL))
    rows = (await session.execute(_SHERIFF_JOIN_SQL, {"ingest_run_id": ingest_run_id})).all()

    events = 0
    if dataset_seen:
        for row in rows:
            if row.row_exists:
                continue
            draft = sheriff_sale_event(
                row.case_number,
                row.sale_date.isoformat() if row.sale_date else None,
                row.sale_type,
                _as_float(row.opening_bid),
            )
            session.add(
                ParcelEvent(
                    parcel_number=row.parcel_number,
                    dataset=SHERIFF_DATASET,
                    code=draft.code,
                    severity=draft.severity,
                    old_value=draft.old_value,
                    new_value=draft.new_value,
                    ingest_run_id=ingest_run_id,
                )
            )
            events += 1
        await session.flush()

    changes = (await session.execute(_SHERIFF_CHANGES_SQL, {"ingest_run_id": ingest_run_id})).all()
    for change in changes:
        session.add(
            SheriffSaleEvent(
                parcel_number=change.parcel_number,
                case_number=change.case_number,
                sale_date=change.new_sale_date or change.old_sale_date,
                old_status=change.old_status,
                new_status=change.new_status,
                old_sale_date=change.old_sale_date,
                new_sale_date=change.new_sale_date,
            )
        )
    if changes:
        await session.flush()

    await session.execute(_UPSERT_SHERIFF_SQL, {"ingest_run_id": ingest_run_id})
    return MergeResult(merged_rows=len(rows), event_count=events + len(changes))
