from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.buyers.derivation import (
    REPEAT_MIN_PURCHASES,
    REPEAT_WINDOW_MONTHS,
    SHERIFF_DEED_DOCUMENT_TYPE,
    RepeatBuyer,
    RepeatBuyerRow,
    derive_repeat_buyers,
)
from lotscope.core.market import MARKET_CODE
from lotscope.core.sql import normalized_name_sql

SOURCE = "rtt_summary"
SOURCE_URL = "https://opendataphilly.org/datasets/real-estate-transfers/"
MAILING_SOURCE = "opa_properties_public"
MAILING_SOURCE_URL = "https://opendataphilly.org/datasets/philadelphia-properties-and-assessments/"

_VACANT_AT_SALE = "(p.is_vacant IS TRUE OR coalesce(p.improvement_value, 0) = 0)"

_ROWS_SQL = text(
    "SELECT s.grantee, s.parcel_number, p.address, s.sale_date, s.sale_price "
    "FROM sale s JOIN parcel p USING (parcel_number) "
    "WHERE s.document_type = :document_type "
    "AND s.sale_date >= current_date - make_interval(months => :months) "
    f"AND p.market_code = :market_code AND {_VACANT_AT_SALE} "
    "AND s.grantee IS NOT NULL "
    "ORDER BY s.sale_date DESC"
)

_MAILING_SQL = text(
    f"SELECT {normalized_name_sql('owner')} AS buyer_key, mailing_address "
    "FROM parcel WHERE market_code = :market_code "
    "AND mailing_address IS NOT NULL AND owner IS NOT NULL"
)

_TOP_GRANTEES_SQL = text(
    "SELECT s.grantee, count(DISTINCT s.parcel_number) AS deeds, sum(s.sale_price) AS total "
    "FROM sale s JOIN parcel p USING (parcel_number) "
    "WHERE s.document_type = :document_type "
    "AND s.sale_date >= current_date - make_interval(months => :months) "
    f"AND p.market_code = :market_code AND {_VACANT_AT_SALE} "
    "AND s.grantee IS NOT NULL "
    "GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT :limit"
)


async def load_repeat_buyers(
    session: AsyncSession,
    *,
    months: int = REPEAT_WINDOW_MONTHS,
    min_purchases: int = REPEAT_MIN_PURCHASES,
) -> list[RepeatBuyer]:
    params = {
        "document_type": SHERIFF_DEED_DOCUMENT_TYPE,
        "months": months,
        "market_code": MARKET_CODE,
    }
    rows = [
        RepeatBuyerRow(
            grantee=row.grantee,
            parcel_number=row.parcel_number,
            address=row.address,
            sale_date=row.sale_date,
            sale_price=float(row.sale_price or 0.0),
        )
        for row in (await session.execute(_ROWS_SQL, params)).all()
    ]

    mailing: dict[str, list[str]] = defaultdict(list)
    for row in (await session.execute(_MAILING_SQL, {"market_code": MARKET_CODE})).all():
        if row.buyer_key:
            mailing[row.buyer_key].append(row.mailing_address)

    return derive_repeat_buyers(rows, mailing_addresses=dict(mailing), min_purchases=min_purchases)


async def top_grantees(
    session: AsyncSession, *, months: int = REPEAT_WINDOW_MONTHS, limit: int = 30
) -> list[dict[str, object]]:
    rows = (
        await session.execute(
            _TOP_GRANTEES_SQL,
            {
                "document_type": SHERIFF_DEED_DOCUMENT_TYPE,
                "months": months,
                "market_code": MARKET_CODE,
                "limit": limit,
            },
        )
    ).all()
    return [
        {
            "grantee": row.grantee,
            "deeds": int(row.deeds),
            "total_consideration": float(row.total or 0.0),
        }
        for row in rows
    ]


def provenance() -> dict[str, object]:
    return {
        "source": SOURCE,
        "source_url": SOURCE_URL,
        "mailing_source": MAILING_SOURCE,
        "mailing_source_url": MAILING_SOURCE_URL,
        "computed_at": datetime.now(UTC).isoformat(),
        "window_months": REPEAT_WINDOW_MONTHS,
        "document_type": SHERIFF_DEED_DOCUMENT_TYPE,
        "vacancy_rule": (
            "is_vacant is true, or OPA improvement_value is zero at the parcel's current "
            "assessment — the best available stand-in for 'no structure at sale', since the "
            "assessment table holds no historical improvement value"
        ),
    }
