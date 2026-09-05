"""Reads of the primary sources, made while the buyer waits.

The nightly ingest is an index. Owner, last sale, open violations and sale status are the
four facts a buyer checks before they bid, so those are read here from the source itself at
answer time. Every fetcher has an 8 second leash and no retries: a slow answer is worse than
an answer that says the live check did not come back.
"""

from typing import Any
from urllib.parse import urlencode

import httpx

from lotscope.core.config import Settings
from lotscope.core.errors import LotScopeError
from lotscope.ingestion.carto import quote_literal
from lotscope.ingestion.loaders.sheriff_civilview import (
    CivilViewListRow,
    parse_sale_detail,
    parse_sale_list,
)

OPA_TABLE = "opa_properties_public"
RTT_TABLE = "rtt_summary"
# The `violations` table carries casestatus on each violation row, so the case status a
# buyer asks about comes back without a second request. The ArcGIS layer would need one.
LI_TABLE = "violations"

_LIST_PATH = "/Sales/SalesSearch"
_DETAIL_PATH = "/Sales/SaleDetails"


class LiveFetchError(LotScopeError):
    """The primary source did not answer. The caller reports unverified, never guesses."""


def local_key(parcel: str) -> str:
    return parcel.split(":", 1)[-1].strip()


def carto_url(settings: Settings, sql: str) -> str:
    return f"{settings.carto_sql_url}?{urlencode({'q': sql})}"


def opa_sql(parcel: str) -> str:
    return (
        "SELECT parcel_number, owner_1, owner_2, mailing_address_1, mailing_street, "
        "mailing_city_state, mailing_zip, sale_date, sale_price, market_value, "
        "category_code_description FROM opa_properties_public "
        f"WHERE parcel_number = {quote_literal(local_key(parcel))} LIMIT 1"
    )


def rtt_sql(parcel: str) -> str:
    return (
        "SELECT document_id, document_type, recording_date, grantors, grantees, "
        "total_consideration FROM rtt_summary "
        f"WHERE opa_account_num = {quote_literal(local_key(parcel))} "
        "ORDER BY recording_date DESC NULLS LAST LIMIT 5"
    )


def li_sql(parcel: str) -> str:
    return (
        "SELECT violationnumber, violationcodetitle, violationstatus, casestatus, "
        "violationdate FROM violations "
        f"WHERE opa_account_num = {quote_literal(local_key(parcel))} "
        "ORDER BY violationdate DESC NULLS LAST LIMIT 100"
    )


def _client(settings: Settings, transport: httpx.AsyncBaseTransport | None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=settings.live_verify_timeout_seconds,
        transport=transport,
        follow_redirects=True,
    )


async def _carto_rows(
    settings: Settings, sql: str, transport: httpx.AsyncBaseTransport | None
) -> list[dict[str, Any]]:
    try:
        async with _client(settings, transport) as client:
            response = await client.post(settings.carto_sql_url, data={"q": sql})
            response.raise_for_status()
            body = response.json()
    except httpx.TimeoutException as cause:
        raise LiveFetchError(
            f"Carto did not answer within {settings.live_verify_timeout_seconds:.0f}s."
        ) from cause
    except (httpx.HTTPError, ValueError) as cause:
        raise LiveFetchError(f"Carto read failed: {cause}") from cause

    rows = body.get("rows")
    if not isinstance(rows, list):
        raise LiveFetchError("Carto returned a body with no rows.")
    return [row for row in rows if isinstance(row, dict)]


async def fetch_opa(
    settings: Settings, parcel: str, *, transport: httpx.AsyncBaseTransport | None = None
) -> dict[str, Any]:
    sql = opa_sql(parcel)
    rows = await _carto_rows(settings, sql, transport)
    return {"url": carto_url(settings, sql), "row": rows[0] if rows else None}


async def fetch_rtt(
    settings: Settings, parcel: str, *, transport: httpx.AsyncBaseTransport | None = None
) -> dict[str, Any]:
    sql = rtt_sql(parcel)
    return {"url": carto_url(settings, sql), "rows": await _carto_rows(settings, sql, transport)}


async def fetch_li(
    settings: Settings, parcel: str, *, transport: httpx.AsyncBaseTransport | None = None
) -> dict[str, Any]:
    sql = li_sql(parcel)
    return {"url": carto_url(settings, sql), "rows": await _carto_rows(settings, sql, transport)}


def _matches(row: CivilViewListRow, needle: str) -> bool:
    wanted = needle.strip().casefold()
    candidates = (row.case_number, row.opa_number, row.parcel_id)
    return any(value and value.strip().casefold() == wanted for value in candidates)


async def fetch_sheriff(
    settings: Settings, needle: str, *, transport: httpx.AsyncBaseTransport | None = None
) -> dict[str, Any]:
    """Find one listing on the public sale list, then read its detail page.

    CivilView has no lookup by case number, so the list page is the index: one request to
    find the property id, one to read the status and sale date off the detail page.
    """
    base = settings.sheriff_sale_civilview_base_url.rstrip("/")
    wanted = local_key(needle)
    try:
        async with _client(settings, transport) as client:
            listing = await client.get(
                f"{base}{_LIST_PATH}", params={"countyId": str(settings.sheriff_sale_county_id)}
            )
            listing.raise_for_status()
            rows = parse_sale_list(listing.text)
            match = next(
                (row for row in rows if _matches(row, needle) or _matches(row, wanted)), None
            )
            if match is None:
                return {"url": f"{base}{_LIST_PATH}", "listed": False, "detail": None}

            detail_url = f"{base}{_DETAIL_PATH}?PropertyId={match.property_id}"
            detail = await client.get(
                f"{base}{_DETAIL_PATH}", params={"PropertyId": match.property_id}
            )
            detail.raise_for_status()
    except httpx.TimeoutException as cause:
        raise LiveFetchError(
            f"CivilView did not answer within {settings.live_verify_timeout_seconds:.0f}s."
        ) from cause
    except httpx.HTTPError as cause:
        raise LiveFetchError(f"CivilView read failed: {cause}") from cause

    parsed = parse_sale_detail(detail.text)
    return {
        "url": detail_url,
        "listed": True,
        "case_number": match.case_number,
        "address": match.address,
        "detail": parsed.model_dump(),
    }
