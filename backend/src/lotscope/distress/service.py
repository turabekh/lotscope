from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.distress.models import ParcelDistress
from lotscope.distress.profiles import DISTRESS_PROFILE, DistressScoringProfile
from lotscope.distress.schemas import (
    DistressFactor,
    DistressResult,
    LeadItem,
    MailRecipient,
    build_mail_recipients,
)
from lotscope.distress.scoring import (
    DistressSignals,
    is_absentee,
    score_distress,
)
from lotscope.risk.attribution import TransferAfterSnapshot, attribute_delinquency
from lotscope.risk.violation_status import open_violation_sql
from lotscope.verdict.service import DealSignal, get_deal_signals

_SOURCES: list[dict[str, Any]] = [
    {"source": "tax_status"},
    {"source": "li_event"},
    {"source": "parcel"},
    {"source": "sale"},
]

_ARMS_LENGTH_MIN_PRICE = 1000

_TENURE_JOIN = (
    "LEFT JOIN (SELECT parcel_number, max(sale_date) AS last_sale_date FROM sale "
    "WHERE sale_date IS NOT NULL AND document_type ILIKE '%DEED%' "
    f"AND (sale_price IS NULL OR sale_price >= {_ARMS_LENGTH_MIN_PRICE}) "
    "AND parcel_number = {filter} GROUP BY parcel_number) sl "
    "ON sl.parcel_number = p.parcel_number"
)

_TIRED_OWNERS_SUBQUERY = (
    "SELECT tp.owner_key FROM parcel tp "
    "LEFT JOIN (SELECT parcel_number, count(*) AS open_violations FROM li_event "
    "WHERE event_type = 'violation' AND " + open_violation_sql("li_event") + " "
    "GROUP BY parcel_number) tv ON tv.parcel_number = tp.parcel_number "
    "WHERE tp.owner_key IS NOT NULL "
    "GROUP BY tp.owner_key "
    "HAVING count(*) >= 3 AND coalesce(sum(tv.open_violations), 0) >= 5"
)

_TIRED_OWNERS_SQL = text(_TIRED_OWNERS_SUBQUERY)

_ONE_OWNER_TIRED_SQL = text(
    "SELECT (count(*) >= 3 AND coalesce(sum(v.open_violations), 0) >= 5) AS tired "
    "FROM parcel p "
    "LEFT JOIN (SELECT parcel_number, count(*) AS open_violations FROM li_event "
    "WHERE event_type = 'violation' AND " + open_violation_sql("li_event") + " "
    "GROUP BY parcel_number) v ON v.parcel_number = p.parcel_number "
    "WHERE p.owner_key = :owner_key"
)

_PARCEL_DISTRESS_SQL = text(
    "SELECT p.market_code, p.is_vacant, p.is_city_owned, p.address, p.mailing_address, "
    "p.owner_key, "
    "ts.is_delinquent, ts.total_due, ts.years_owed, ts.lien_count, ts.in_sheriff_sale, "
    "ts.delinquency_owner, ts.snapshot_period, p.owner AS current_owner, "
    "d.grantor, d.document_type, d.document_id, d.sale_date, d.sale_price, "
    "coalesce(li.dangerous, false) AS dangerous, "
    "coalesce(li.open_violations, 0) AS open_violations, "
    "coalesce(li.violations_on_record, 0) AS violations_on_record, "
    "coalesce(li.demolitions, 0) AS demolitions, "
    "(CURRENT_DATE - sl.last_sale_date)::float / 365.25 AS years_since_last_sale "
    "FROM parcel p "
    "LEFT JOIN tax_status ts ON ts.parcel_number = p.parcel_number "
    "LEFT JOIN LATERAL ("
    "  SELECT s.grantor, s.document_type, s.document_id, s.sale_date, s.sale_price "
    "  FROM sale s WHERE s.parcel_number = p.parcel_number "
    "  AND ts.snapshot_period IS NOT NULL "
    "  AND s.sale_date >= (to_date(ts.snapshot_period, 'YYYYMM') "
    "      + interval '1 month')::date "
    "  ORDER BY s.sale_date ASC LIMIT 1"
    ") d ON TRUE "
    "LEFT JOIN ("
    "  SELECT parcel_number, "
    "  bool_or(coalesce(is_unsafe, false) OR coalesce(is_imminently_dangerous, false)) "
    "  AS dangerous, "
    "  count(*) FILTER (WHERE event_type = 'violation' AND "
    + open_violation_sql("li_event")
    + ") AS open_violations, "
    "  count(*) FILTER (WHERE event_type = 'violation') AS violations_on_record, "
    "  count(*) FILTER (WHERE event_type = 'demolition') AS demolitions "
    "  FROM li_event WHERE parcel_number = :parcel_number GROUP BY parcel_number"
    ") li ON li.parcel_number = p.parcel_number "
    + _TENURE_JOIN.format(filter=":parcel_number")
    + " WHERE p.parcel_number = :parcel_number"
)

_BULK_SIGNALS_SQL = text(
    "SELECT p.parcel_number, p.market_code, p.is_vacant, p.is_city_owned, p.address, "
    "p.mailing_address, p.owner_key, "
    "ts.is_delinquent, ts.total_due, ts.years_owed, ts.lien_count, ts.in_sheriff_sale, "
    "ts.delinquency_owner, ts.snapshot_period, p.owner AS current_owner, "
    "d.grantor, d.document_type, d.document_id, d.sale_date, d.sale_price, "
    "coalesce(li.dangerous, false) AS dangerous, "
    "coalesce(li.open_violations, 0) AS open_violations, "
    "coalesce(li.violations_on_record, 0) AS violations_on_record, "
    "coalesce(li.demolitions, 0) AS demolitions, "
    "(CURRENT_DATE - sl.last_sale_date)::float / 365.25 AS years_since_last_sale "
    "FROM parcel p "
    "LEFT JOIN tax_status ts ON ts.parcel_number = p.parcel_number "
    "LEFT JOIN LATERAL ("
    "  SELECT s.grantor, s.document_type, s.document_id, s.sale_date, s.sale_price "
    "  FROM sale s WHERE s.parcel_number = p.parcel_number "
    "  AND ts.snapshot_period IS NOT NULL "
    "  AND s.sale_date >= (to_date(ts.snapshot_period, 'YYYYMM') "
    "      + interval '1 month')::date "
    "  ORDER BY s.sale_date ASC LIMIT 1"
    ") d ON TRUE "
    "LEFT JOIN ("
    "  SELECT parcel_number, "
    "  bool_or(coalesce(is_unsafe, false) OR coalesce(is_imminently_dangerous, false)) "
    "  AS dangerous, "
    "  count(*) FILTER (WHERE event_type = 'violation' AND "
    + open_violation_sql("li_event")
    + ") AS open_violations, "
    "  count(*) FILTER (WHERE event_type = 'violation') AS violations_on_record, "
    "  count(*) FILTER (WHERE event_type = 'demolition') AS demolitions "
    "  FROM li_event WHERE parcel_number = ANY(:parcel_numbers) GROUP BY parcel_number"
    ") li ON li.parcel_number = p.parcel_number "
    + _TENURE_JOIN.format(filter="ANY(:parcel_numbers)")
    + " WHERE p.parcel_number = ANY(:parcel_numbers)"
)

_ATTRIBUTED_DUE_SQL = "CASE WHEN pd.debt_counts THEN ts.total_due END"

_LEADS_SQL = text(
    "SELECT p.parcel_number, p.address, p.mailing_address, p.owner, "
    "coalesce(nullif(p.base_zoning_code, ''), p.resolved_zoning_code) AS base_zoning_code, "
    "p.is_vacant, p.market_value, " + _ATTRIBUTED_DUE_SQL + " AS total_due, "
    "ts.in_sheriff_sale, pd.score, "
    "(tired.owner_key IS NOT NULL) AS is_tired_landlord, "
    "(SELECT (CURRENT_DATE - max(s.sale_date))::float / 365.25 FROM sale s "
    "WHERE s.parcel_number = p.parcel_number AND s.sale_date IS NOT NULL "
    "AND s.document_type ILIKE '%DEED%' "
    f"AND (s.sale_price IS NULL OR s.sale_price >= {_ARMS_LENGTH_MIN_PRICE})) "
    "AS years_since_last_sale "
    "FROM parcel_distress pd "
    "JOIN parcel p ON p.parcel_number = pd.parcel_number "
    "LEFT JOIN tax_status ts ON ts.parcel_number = p.parcel_number "
    "LEFT JOIN (" + _TIRED_OWNERS_SUBQUERY + ") tired ON tired.owner_key = p.owner_key "
    "WHERE pd.score >= CAST(:min_score AS integer) "
    "AND p.market_code = CAST(:market_code AS text) "
    "AND coalesce(p.is_city_owned, false) = false "
    "AND (NOT CAST(:vacant_only AS boolean) OR coalesce(p.is_vacant, false)) "
    "AND (CAST(:zip_code AS text) IS NULL OR p.zip_code = CAST(:zip_code AS text)) "
    "ORDER BY pd.score DESC, coalesce(" + _ATTRIBUTED_DUE_SQL + ", 0) DESC, p.parcel_number "
    "LIMIT CAST(:limit AS integer)"
)

_LEADS_EXPORT_SQL = text(
    "SELECT p.parcel_number, p.address, p.owner, p.mailing_address, p.zip_code, "
    "coalesce(nullif(p.base_zoning_code, ''), p.resolved_zoning_code) AS base_zoning_code, "
    "p.is_vacant, p.market_value, " + _ATTRIBUTED_DUE_SQL + " AS total_due, "
    "ts.in_sheriff_sale, pd.score "
    "FROM parcel_distress pd "
    "JOIN parcel p ON p.parcel_number = pd.parcel_number "
    "LEFT JOIN tax_status ts ON ts.parcel_number = p.parcel_number "
    "WHERE pd.score >= CAST(:min_score AS integer) "
    "AND p.market_code = CAST(:market_code AS text) "
    "AND coalesce(p.is_city_owned, false) = false "
    "AND (NOT CAST(:vacant_only AS boolean) OR coalesce(p.is_vacant, false)) "
    "AND (CAST(:zip_code AS text) IS NULL OR p.zip_code = CAST(:zip_code AS text)) "
    "ORDER BY pd.score DESC, coalesce(" + _ATTRIBUTED_DUE_SQL + ", 0) DESC, p.parcel_number "
    "LIMIT CAST(:limit AS integer)"
)

LEADS_EXPORT_HEADER: list[str] = [
    "parcel_number",
    "address",
    "owner",
    "mailing_address",
    "zip_code",
    "zoning",
    "vacant",
    "assessed_value",
    "distress_score",
    "total_due",
    "in_sheriff_sale",
]


async def list_mail_recipients(
    session: AsyncSession,
    *,
    row_limit: int,
    market_code: str = "phl",
    min_score: int = 1,
    vacant_only: bool = False,
    zip_code: str | None = None,
    one_per_owner: bool = False,
) -> list[MailRecipient]:
    if row_limit <= 0:
        return []
    rows = (
        await session.execute(
            _LEADS_EXPORT_SQL,
            {
                "limit": row_limit,
                "market_code": market_code,
                "min_score": min_score,
                "vacant_only": vacant_only,
                "zip_code": zip_code,
            },
        )
    ).all()
    return build_mail_recipients(rows, one_per_owner=one_per_owner)


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def _yes_no(value: Any) -> str:
    if value is None:
        return ""
    return "Yes" if value else "No"


def _delinquency_counts(row: Row[Any]) -> bool:
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
    return attribute_delinquency(
        delinquency_owner=row.delinquency_owner,
        current_owner=row.current_owner,
        snapshot_period=row.snapshot_period,
        transfer=transfer,
    ).counts_toward_distress


def _signals(row: Row[Any], tired_owner_keys: frozenset[str]) -> DistressSignals:
    return DistressSignals(
        in_sheriff_sale=bool(row.in_sheriff_sale),
        is_delinquent=bool(row.is_delinquent) and _delinquency_counts(row),
        total_due=_as_float(row.total_due),
        years_owed=row.years_owed,
        lien_count=row.lien_count,
        has_imminently_dangerous=bool(row.dangerous),
        open_violations=row.open_violations,
        violations_on_record=row.violations_on_record,
        demolitions=row.demolitions,
        is_vacant=bool(row.is_vacant),
        is_absentee_owner=is_absentee(row.address, row.mailing_address),
        is_city_owned=bool(row.is_city_owned),
        years_since_last_sale=_as_float(row.years_since_last_sale),
        is_tired_landlord=row.owner_key is not None and row.owner_key in tired_owner_keys,
    )


async def tired_landlord_owner_keys(session: AsyncSession) -> frozenset[str]:
    rows = (await session.execute(_TIRED_OWNERS_SQL)).all()
    return frozenset(row.owner_key for row in rows)


async def _owner_is_tired(session: AsyncSession, owner_key: str | None) -> bool:
    if owner_key is None:
        return False
    return bool(await session.scalar(_ONE_OWNER_TIRED_SQL, {"owner_key": owner_key}))


async def assess_parcel_distress(
    session: AsyncSession, parcel_number: str
) -> DistressResult | None:
    row = (
        await session.execute(_PARCEL_DISTRESS_SQL, {"parcel_number": parcel_number})
    ).one_or_none()
    if row is None:
        return None
    tired = await _owner_is_tired(session, row.owner_key)
    tired_owner_keys = frozenset({row.owner_key}) if tired and row.owner_key else frozenset()
    assessment = score_distress(_signals(row, tired_owner_keys), DISTRESS_PROFILE)
    return DistressResult(
        parcel_number=parcel_number,
        score=assessment.score,
        tier=assessment.tier,
        factors=[
            DistressFactor(code=f.code, label=f.label, weight=f.weight) for f in assessment.factors
        ],
        sources=_SOURCES,
        computed_at=datetime.now(UTC),
    )


async def recompute_distress(
    session: AsyncSession,
    parcel_numbers: Sequence[str],
    tired_owner_keys: frozenset[str] = frozenset(),
) -> int:
    if not parcel_numbers:
        return 0
    rows = (
        await session.execute(_BULK_SIGNALS_SQL, {"parcel_numbers": list(parcel_numbers)})
    ).all()
    if not rows:
        return 0
    now = datetime.now(UTC)
    values = []
    for row in rows:
        signals = _signals(row, tired_owner_keys)
        assessment = score_distress(signals, DISTRESS_PROFILE)
        values.append(
            {
                "parcel_number": row.parcel_number,
                "score": assessment.score,
                "tier": assessment.tier,
                "sources": _SOURCES,
                "debt_counts": signals.is_delinquent,
                "computed_at": now,
            }
        )
    statement = insert(ParcelDistress).values(values)
    statement = statement.on_conflict_do_update(
        index_elements=["parcel_number"],
        set_={
            "score": statement.excluded.score,
            "tier": statement.excluded.tier,
            "sources": statement.excluded.sources,
            "debt_counts": statement.excluded.debt_counts,
            "computed_at": statement.excluded.computed_at,
            # `onupdate` is an UPDATE-construct hook and an upsert is an INSERT, so
            # without this the column keeps the value from the row's first write and
            # reads as though the score has not been touched since.
            "updated_at": now,
        },
    )
    await session.execute(statement)
    return len(values)


def _lead_top_factors(row: Row[Any], profile: DistressScoringProfile) -> list[str]:
    factors: list[str] = []
    if row.in_sheriff_sale:
        factors.append("Sheriff sale")
    if row.is_tired_landlord:
        factors.append("Tired landlord")
    if (
        is_absentee(row.address, row.mailing_address)
        and row.years_since_last_sale is not None
        and row.years_since_last_sale >= profile.long_tenure_years
    ):
        factors.append(f"Long-held (~{int(row.years_since_last_sale)} yrs)")
    if row.total_due:
        factors.append(f"${float(row.total_due):,.0f} owed")
    if row.is_vacant:
        factors.append("Vacant")
    return factors


async def find_leads(
    session: AsyncSession,
    *,
    limit: int,
    market_code: str = "phl",
    min_score: int = 1,
    vacant_only: bool = False,
    zip_code: str | None = None,
) -> list[LeadItem]:
    rows = (
        await session.execute(
            _LEADS_SQL,
            {
                "limit": limit,
                "market_code": market_code,
                "min_score": min_score,
                "vacant_only": vacant_only,
                "zip_code": zip_code,
            },
        )
    ).all()
    signals = await get_deal_signals(session, [row.parcel_number for row in rows])
    return [_lead_item(row, signals.get(row.parcel_number), DISTRESS_PROFILE) for row in rows]


async def export_leads(
    session: AsyncSession,
    *,
    row_limit: int,
    market_code: str = "phl",
    min_score: int = 1,
    vacant_only: bool = False,
    zip_code: str | None = None,
) -> list[tuple[Any, ...]]:
    if row_limit <= 0:
        return []
    rows = (
        await session.execute(
            _LEADS_EXPORT_SQL,
            {
                "limit": row_limit,
                "market_code": market_code,
                "min_score": min_score,
                "vacant_only": vacant_only,
                "zip_code": zip_code,
            },
        )
    ).all()
    return [
        (
            row.parcel_number,
            row.address,
            row.owner,
            row.mailing_address,
            row.zip_code,
            row.base_zoning_code,
            _yes_no(row.is_vacant),
            _as_float(row.market_value),
            int(row.score),
            _as_float(row.total_due),
            _yes_no(row.in_sheriff_sale),
        )
        for row in rows
    ]


def _lead_item(
    row: Row[Any], signal: DealSignal | None, profile: DistressScoringProfile
) -> LeadItem:
    return LeadItem(
        parcel_number=row.parcel_number,
        address=row.address,
        owner=row.owner,
        base_zoning_code=row.base_zoning_code,
        is_vacant=row.is_vacant,
        market_value=_as_float(row.market_value),
        total_due=_as_float(row.total_due),
        in_sheriff_sale=row.in_sheriff_sale,
        score=int(row.score),
        top_factors=_lead_top_factors(row, profile),
        deal_score=signal.deal_score if signal is not None else None,
        max_allowable_offer=signal.max_allowable_offer if signal is not None else None,
        is_underpriced=signal.is_underpriced if signal is not None else None,
    )
