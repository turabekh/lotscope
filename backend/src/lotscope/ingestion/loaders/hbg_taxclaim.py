from datetime import date
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.extract import ExtractClient
from lotscope.ingestion.normalizers import get_normalizer
from lotscope.ingestion.service import record_freshness
from lotscope.ingestion.upsert import upsert
from lotscope.parcels.models import Parcel
from lotscope.risk.models import TaxStatus

HBG_TAX_CLAIM_DATASET = "dc_tax_claim"
_MARKET = "hbg"

FORCED_SALE_TYPES = frozenset({"upset", "judicial"})
_KNOWN_TYPES = FORCED_SALE_TYPES | {"repository"}


def _amount(value: Any) -> float | None:
    if value in (None, ""):
        return None
    cleaned = str(value).replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def classify_tax_claim_row(row: dict[str, Any]) -> dict[str, Any] | None:
    local = get_normalizer(_MARKET).normalize_local_key(row.get("parcel_id"))
    sale_type = str(row.get("sale_type", "")).strip().lower()
    if local is None or sale_type not in _KNOWN_TYPES:
        return None
    return {
        "parcel_number": f"{_MARKET}:{local}",
        "sale_type": sale_type,
        "amount_due": _amount(row.get("amount_due")),
    }


def repository_parcel_numbers(classified: list[dict[str, Any]]) -> list[str]:
    return [c["parcel_number"] for c in classified if c["sale_type"] == "repository"]


def tax_status_row(record: dict[str, Any], list_date: date) -> dict[str, Any] | None:
    if record["sale_type"] not in FORCED_SALE_TYPES:
        return None
    return {
        "parcel_number": record["parcel_number"],
        "is_delinquent": True,
        "in_sheriff_sale": True,
        "total_due": record["amount_due"],
        "as_of_date": list_date,
    }


async def load_hbg_tax_claim(
    session: AsyncSession,
    extract: ExtractClient,
    *,
    list_url: str,
    list_date: date,
) -> int:
    known = await session.execute(select(Parcel.parcel_number).where(Parcel.market_code == _MARKET))
    known_parcels = set(known.scalars())
    _, raw_rows = await extract.fetch_csv_records(list_url)
    classified = [
        c
        for row in raw_rows
        if (c := classify_tax_claim_row(row)) is not None and c["parcel_number"] in known_parcels
    ]
    tax_rows = [t for record in classified if (t := tax_status_row(record, list_date)) is not None]
    if tax_rows:
        await upsert(
            session,
            TaxStatus,
            tax_rows,
            index_elements=["parcel_number"],
            update_columns=["is_delinquent", "in_sheriff_sale", "total_due", "as_of_date"],
        )
    repository = repository_parcel_numbers(classified)
    if repository:
        await session.execute(
            update(Parcel)
            .where(Parcel.parcel_number.in_(repository))
            .values(is_city_owned=True)
        )
    await record_freshness(
        session,
        HBG_TAX_CLAIM_DATASET,
        status="success",
        success=True,
        market_code=_MARKET,
        row_count=len(tax_rows),
        detail=f"as of {list_date.isoformat()}",
    )
    return len(tax_rows)
