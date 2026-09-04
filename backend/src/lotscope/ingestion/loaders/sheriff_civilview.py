import asyncio
from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel
from selectolax.parser import HTMLParser

from lotscope.core.config import Settings
from lotscope.core.errors import LotScopeError
from lotscope.ingestion.http import request_with_retry

CIVILVIEW_DATASET = "sheriff_sale"

_LIST_PATH = "/Sales/SalesSearch"
_DETAIL_PATH = "/Sales/SaleDetails"
_PROPERTY_ID_PARAM = "PropertyId"
_COUNTY_ID_PARAM = "countyId"


class CivilViewError(LotScopeError): ...


class CivilViewListRow(BaseModel):
    property_id: str
    case_number: str | None = None
    opa_number: str | None = None
    parcel_id: str | None = None
    address: str | None = None
    plaintiff: str | None = None
    status: str | None = None
    sale_date: str | None = None


class CivilViewDetail(BaseModel):
    sale_date: str | None = None
    sale_type: str | None = None
    status: str | None = None
    opening_bid: float | None = None


def _clean(text: str | None) -> str | None:
    if text is None:
        return None
    collapsed = " ".join(text.split())
    return collapsed or None


def _property_id_from_href(href: str | None) -> str | None:
    if not href or _PROPERTY_ID_PARAM not in href:
        return None
    _, _, query = href.partition("?")
    for part in query.split("&"):
        key, _, value = part.partition("=")
        if key == _PROPERTY_ID_PARAM and value:
            return value
    return None


def parse_us_date(raw: str | None) -> str | None:
    cleaned = _clean(raw)
    if not cleaned:
        return None
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_currency(raw: str | None) -> float | None:
    cleaned = _clean(raw)
    if not cleaned:
        return None
    stripped = cleaned.replace("$", "").replace(",", "").strip()
    if not stripped:
        return None
    try:
        return float(stripped)
    except ValueError:
        return None


def parse_sale_list(html: str) -> list[CivilViewListRow]:
    tree = HTMLParser(html)
    rows: list[CivilViewListRow] = []
    for tr in tree.css("tr"):
        anchor = tr.css_first("a[href*='SaleDetails']")
        if anchor is None:
            continue
        property_id = _property_id_from_href(anchor.attributes.get("href"))
        if property_id is None:
            continue
        cells = [_clean(td.text()) for td in tr.css("td")]
        columns = cells[1:] if cells else []
        rows.append(
            CivilViewListRow(
                property_id=property_id,
                case_number=columns[0] if len(columns) > 0 else None,
                opa_number=columns[1] if len(columns) > 1 else None,
                address=columns[2] if len(columns) > 2 else None,
                plaintiff=columns[3] if len(columns) > 3 else None,
            )
        )
    return rows


def _detail_fields(tree: HTMLParser) -> dict[str, str]:
    fields: dict[str, str] = {}
    for item in tree.css(".sale-detail-item"):
        label = item.css_first(".sale-detail-label")
        value = item.css_first(".sale-detail-value")
        if label is None or value is None:
            continue
        key = _clean(label.text())
        if not key:
            continue
        normalized = key.rstrip(":").strip().casefold()
        fields[normalized] = _clean(value.text()) or ""
    return fields


def _current_status(tree: HTMLParser) -> str | None:
    for tr in tree.css("tr"):
        cells = tr.css("td")
        if len(cells) != 2:
            continue
        status = _clean(cells[0].text())
        when = parse_us_date(cells[1].text())
        if status and when:
            return status
    return None


def parse_sale_detail(html: str) -> CivilViewDetail:
    tree = HTMLParser(html)
    fields = _detail_fields(tree)
    return CivilViewDetail(
        sale_date=parse_us_date(fields.get("sales date")),
        sale_type=fields.get("sale type") or None,
        status=_current_status(tree),
        opening_bid=parse_currency(fields.get("minimum bid")),
    )


def civilview_record(row: CivilViewListRow, detail: CivilViewDetail) -> dict[str, Any]:
    return {
        "case_number": row.case_number,
        "opa_number": row.opa_number,
        "address": row.address,
        "plaintiff": row.plaintiff,
        "sale_type": detail.sale_type,
        "status": detail.status,
        "sale_date": detail.sale_date,
        "opening_bid": detail.opening_bid,
    }


class CivilViewSheriffSource:
    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
        *,
        county_id: int | None = None,
    ) -> None:
        self._base_url = settings.sheriff_sale_civilview_base_url.rstrip("/")
        self._county_id = county_id if county_id is not None else settings.sheriff_sale_county_id
        self._max_retries = settings.http_max_retries
        self._backoff = settings.http_backoff_seconds
        self._timeout = settings.http_timeout_seconds
        self._request_delay = settings.sheriff_sale_civilview_request_delay_seconds
        self._detail_limit = settings.sheriff_sale_civilview_detail_limit
        self._transport = transport

    async def _get(self, client: httpx.AsyncClient, url: str, params: dict[str, str]) -> str:
        response = await request_with_retry(
            lambda: client.get(url, params=params),
            max_retries=self._max_retries,
            backoff=self._backoff,
            error=CivilViewError,
        )
        return response.text

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            follow_redirects=True, timeout=self._timeout, transport=self._transport
        )

    async def fetch_list(self) -> list[CivilViewListRow]:
        list_url = f"{self._base_url}{_LIST_PATH}"
        async with self._client() as client:
            list_html = await self._get(client, list_url, {_COUNTY_ID_PARAM: str(self._county_id)})
        return parse_sale_list(list_html)

    async def fetch(self) -> list[dict[str, Any]]:
        list_url = f"{self._base_url}{_LIST_PATH}"
        detail_url = f"{self._base_url}{_DETAIL_PATH}"
        records: list[dict[str, Any]] = []
        async with self._client() as client:
            list_html = await self._get(client, list_url, {_COUNTY_ID_PARAM: str(self._county_id)})
            rows = parse_sale_list(list_html)
            if self._detail_limit is not None:
                rows = rows[: self._detail_limit]
            for row in rows:
                if self._request_delay:
                    await asyncio.sleep(self._request_delay)
                detail_html = await self._get(
                    client, detail_url, {_PROPERTY_ID_PARAM: row.property_id}
                )
                records.append(civilview_record(row, parse_sale_detail(detail_html)))
        return records
