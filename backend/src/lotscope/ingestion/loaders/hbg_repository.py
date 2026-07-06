import csv
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.normalizers import get_normalizer
from lotscope.ingestion.service import record_freshness
from lotscope.ingestion.upsert import upsert
from lotscope.parcels.models import Parcel
from lotscope.risk.models import RepositoryListing

HBG_REPOSITORY_DATASET = "dc_repository"
_MARKET = "hbg"
_TRUE = frozenset({"true", "yes", "1", "y", "t"})


@dataclass(frozen=True)
class RepositoryLoadResult:
    loaded: int
    skipped_non_city: int
    skipped_unknown_parcel: int
    list_as_of: date | None


def _is_harrisburg_city(municipality: str | None) -> bool:
    upper = (municipality or "").upper()
    return "HBG" in upper or "HARRISBURG" in upper


def _text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value).strip() or None


def _bool(value: Any) -> bool:
    return str(value).strip().lower() in _TRUE


def _date(value: Any) -> date | None:
    text = _text(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def classify_repository_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    if not _is_harrisburg_city(row.get("municipality")):
        return None
    local = get_normalizer(_MARKET).normalize_local_key(row.get("parcel_number"))
    if local is None:
        return None
    return {
        "parcel_number": f"{_MARKET}:{local}",
        "city_status": _text(row.get("hbg_city_status")),
        "bid_pending": _bool(row.get("bid_pending")),
        "list_as_of": _date(row.get("list_as_of")),
        "source_url": _text(row.get("source_url")),
        "source": HBG_REPOSITORY_DATASET,
    }


def read_repository_csv(path: str | Path) -> list[dict[str, Any]]:
    with open(path, newline="") as handle:
        return list(csv.DictReader(handle))


async def load_hbg_repository(
    session: AsyncSession, rows: Iterable[Mapping[str, Any]]
) -> RepositoryLoadResult:
    known = await session.execute(select(Parcel.parcel_number).where(Parcel.market_code == _MARKET))
    known_parcels = set(known.scalars())

    classified: list[dict[str, Any]] = []
    skipped_non_city = 0
    for row in rows:
        record = classify_repository_row(row)
        if record is None:
            skipped_non_city += 1
        else:
            classified.append(record)

    to_load = [r for r in classified if r["parcel_number"] in known_parcels]
    skipped_unknown = len(classified) - len(to_load)
    list_as_of = next((r["list_as_of"] for r in to_load if r["list_as_of"] is not None), None)

    if to_load:
        await upsert(
            session,
            RepositoryListing,
            to_load,
            index_elements=["parcel_number"],
            update_columns=["city_status", "bid_pending", "list_as_of", "source_url", "source"],
        )
    await record_freshness(
        session,
        HBG_REPOSITORY_DATASET,
        status="success",
        success=True,
        market_code=_MARKET,
        row_count=len(to_load),
        detail=f"as of {list_as_of.isoformat()}" if list_as_of else None,
    )
    return RepositoryLoadResult(
        loaded=len(to_load),
        skipped_non_city=skipped_non_city,
        skipped_unknown_parcel=skipped_unknown,
        list_as_of=list_as_of,
    )


_PARCEL_RE = re.compile(r"\b(\d{2}-\d{3}-\d{3})\b")
_STATUS_RE = re.compile(r"\b(Demolished|Condemned)\b", re.IGNORECASE)
REPOSITORY_PDF_URL = (
    "https://www.dauphincounty.gov/docs/default-source/default-document-library/"
    "master---repo-list-updated.pdf"
)


def parse_repository_pdf_text(text: str, *, list_as_of: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        match = _PARCEL_RE.search(line)
        if match is None:
            continue
        is_city = "HBG" in line.upper() or "HARRISBURG" in line.upper()
        status = _STATUS_RE.search(line)
        rows.append(
            {
                "parcel_number": match.group(1),
                "site_address": None,
                "municipality": "City of Hbg." if is_city else "",
                "assessed_type": "Land",
                "hbg_city_status": status.group(1).capitalize() if status else None,
                "bid_pending": "false",
                "list_as_of": list_as_of,
                "source_url": REPOSITORY_PDF_URL,
            }
        )
    return rows
