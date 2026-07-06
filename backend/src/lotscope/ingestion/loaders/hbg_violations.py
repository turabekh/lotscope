from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.normalizers import get_normalizer
from lotscope.ingestion.service import record_freshness
from lotscope.ingestion.upsert import upsert
from lotscope.parcels.models import Parcel
from lotscope.risk.models import LiEvent

HBG_VIOLATIONS_DATASET = "hbg_code_violations"
_MARKET = "hbg"


@dataclass(frozen=True)
class ViolationFieldMap:
    parcel_id: str
    external_id: str
    violation_type: str
    status: str
    opened: str
    closed: str | None = None


def _text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value).strip()


def _parse_date(value: Any) -> date | None:
    text = _text(value)
    if text is None:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
        try:
            return date.fromisoformat(text) if fmt == "%Y-%m-%d" else _strptime(text, fmt)
        except ValueError:
            continue
    return None


def _strptime(text: str, fmt: str) -> date:
    from datetime import datetime

    return datetime.strptime(text, fmt).date()


def _normalize_status(value: Any) -> str | None:
    text = _text(value)
    if text is None:
        return None
    lowered = text.lower()
    if any(k in lowered for k in ("open", "active", "outstanding", "unresolved")):
        return "OPEN"
    if any(k in lowered for k in ("closed", "complied", "resolved", "abated", "cleared")):
        return "CLOSED"
    return text.upper()


def map_violation_row(
    row: Mapping[str, Any], field_map: ViolationFieldMap
) -> dict[str, Any] | None:
    local = get_normalizer(_MARKET).normalize_local_key(row.get(field_map.parcel_id))
    external = _text(row.get(field_map.external_id))
    if local is None or external is None:
        return None
    closed = _parse_date(row.get(field_map.closed)) if field_map.closed else None
    return {
        "parcel_number": f"{_MARKET}:{local}",
        "external_id": external,
        "event_type": "violation",
        "status": _normalize_status(row.get(field_map.status)),
        "event_date": _parse_date(row.get(field_map.opened)) or closed,
        "description": _text(row.get(field_map.violation_type)),
        "source": HBG_VIOLATIONS_DATASET,
    }


async def load_hbg_violations(
    session: AsyncSession,
    records: Iterable[Mapping[str, Any]],
    *,
    field_map: ViolationFieldMap,
    list_date: date,
) -> int:
    known = await session.execute(select(Parcel.parcel_number).where(Parcel.market_code == _MARKET))
    known_parcels = set(known.scalars())
    rows = [
        row
        for record in records
        if (row := map_violation_row(record, field_map)) is not None
        and row["parcel_number"] in known_parcels
    ]
    if rows:
        await upsert(
            session,
            LiEvent,
            rows,
            index_elements=["event_type", "external_id"],
            update_columns=["parcel_number", "status", "event_date", "description", "source"],
        )
    await record_freshness(
        session,
        HBG_VIOLATIONS_DATASET,
        status="success",
        success=True,
        market_code=_MARKET,
        row_count=len(rows),
        detail=f"as of {list_date.isoformat()}",
    )
    return len(rows)
