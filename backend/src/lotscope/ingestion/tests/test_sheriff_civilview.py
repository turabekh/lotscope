from pathlib import Path

import httpx

from lotscope.core.config import Settings
from lotscope.ingestion.loaders.sheriff import SheriffSaleRecord, to_sheriff_row
from lotscope.ingestion.loaders.sheriff_civilview import (
    CivilViewDetail,
    CivilViewListRow,
    CivilViewSheriffSource,
    civilview_record,
    parse_currency,
    parse_sale_detail,
    parse_sale_list,
    parse_us_date,
)

_FIXTURES = Path(__file__).parent / "fixtures" / "civilview"


def _fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def test_parse_us_date_handles_civilview_and_junk() -> None:
    assert parse_us_date("7/15/2026") == "2026-07-15"
    assert parse_us_date("07/05/2026") == "2026-07-05"
    assert parse_us_date("") is None
    assert parse_us_date(None) is None
    assert parse_us_date("to be announced") is None


def test_parse_currency_strips_symbols() -> None:
    assert parse_currency("$1,600.00") == 1600.0
    assert parse_currency("$12,345.67") == 12345.67
    assert parse_currency("") is None
    assert parse_currency(None) is None
    assert parse_currency("N/A") is None


def test_parse_sale_list_reads_real_rows() -> None:
    rows = parse_sale_list(_fixture("list_county60.html"))
    assert len(rows) == 6
    first = rows[0]
    assert first.property_id == "2049301182"
    assert first.case_number == "2407-031"
    assert first.opa_number == "191165600"
    assert first.address == "2346 NORTH BODINE STREET PHILADELPHIA PA 19133-3311"
    assert first.plaintiff == "CITY OF PHILADELPHIA"


def test_parse_sale_detail_reads_real_detail() -> None:
    detail = parse_sale_detail(_fixture("detail_2049301182.html"))
    assert detail.sale_date == "2026-07-15"
    assert detail.sale_type == "TAX DELINQUENT"
    assert detail.status == "Postponed"
    assert detail.opening_bid == 1600.0


_DETAIL_NO_BID_HTML = (
    "<html><body>"
    "<table><tr><td>Postponed</td><td>9/16/2026</td></tr></table>"
    '<div class="sale-detail-item">'
    '<div class="sale-detail-label">Sales Date:</div>'
    '<div class="sale-detail-value">9/16/2026</div></div>'
    '<div class="sale-detail-item">'
    '<div class="sale-detail-label">Sale Type:</div>'
    '<div class="sale-detail-value">TAX DELINQUENT</div></div>'
    "</body></html>"
)


def test_parse_sale_detail_handles_missing_opening_bid() -> None:
    detail = parse_sale_detail(_DETAIL_NO_BID_HTML)
    assert detail.opening_bid is None
    assert detail.sale_date == "2026-09-16"
    assert detail.sale_type == "TAX DELINQUENT"
    assert detail.status == "Postponed"


def test_civilview_record_merges_into_sheriff_row() -> None:
    row = CivilViewListRow(
        property_id="1",
        case_number="2407-031",
        opa_number="191165600",
        address="2346 NORTH BODINE STREET PHILADELPHIA PA 19133-3311",
        plaintiff="CITY OF PHILADELPHIA",
    )
    detail = CivilViewDetail(
        sale_date="2026-07-15",
        sale_type="TAX DELINQUENT",
        status="Postponed",
        opening_bid=1600.0,
    )
    raw = civilview_record(row, detail)
    mapped = to_sheriff_row(SheriffSaleRecord.model_validate(raw))
    assert mapped is not None
    assert mapped["parcel_number"] == "phl:191165600"
    assert mapped["case_number"] == "2407-031"
    assert mapped["opening_bid"] == 1600.0
    assert mapped["sale_date"].isoformat() == "2026-07-15"


def test_opa_less_row_is_dropped_by_reconciliation() -> None:
    row = CivilViewListRow(property_id="9", case_number="2407-099", opa_number=None)
    raw = civilview_record(row, CivilViewDetail())
    assert to_sheriff_row(SheriffSaleRecord.model_validate(raw)) is None


def test_parse_sale_list_skips_rows_without_detail_link() -> None:
    html = (
        "<table><tbody>"
        "<tr><td>header-ish</td><td>x</td></tr>"
        "<tr><td><a href='/Sales/SaleDetails?PropertyId=42'>View</a></td>"
        "<td>2407-001</td><td></td><td>1 MAIN ST</td><td>CITY</td></tr>"
        "</tbody></table>"
    )
    rows = parse_sale_list(html)
    assert len(rows) == 1
    assert rows[0].property_id == "42"
    assert rows[0].opa_number is None


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        http_backoff_seconds=0.0,
        sheriff_sale_civilview_request_delay_seconds=0.0,
    )


async def test_fetch_primes_list_then_details() -> None:
    list_html = _fixture("list_county60.html")
    detail_html = _fixture("detail_2049301182.html")
    seen: list[str] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path.endswith("/SalesSearch"):
            assert request.url.params.get("countyId") == "60"
            return httpx.Response(200, text=list_html)
        assert request.url.params.get("PropertyId")
        return httpx.Response(200, text=detail_html)

    source = CivilViewSheriffSource(_settings(), transport=httpx.MockTransport(_handler))
    records = await source.fetch()

    assert seen[0].endswith("/SalesSearch")
    assert len(records) == 6
    assert seen.count("/Sales/SaleDetails") == 6
    first = records[0]
    assert first["case_number"] == "2407-031"
    assert first["opa_number"] == "191165600"
    assert first["sale_date"] == "2026-07-15"
    assert first["opening_bid"] == 1600.0


async def test_fetch_respects_detail_limit() -> None:
    list_html = _fixture("list_county60.html")
    detail_html = _fixture("detail_2049301182.html")

    def _handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/SalesSearch"):
            return httpx.Response(200, text=list_html)
        return httpx.Response(200, text=detail_html)

    settings = Settings(
        _env_file=None,
        http_backoff_seconds=0.0,
        sheriff_sale_civilview_request_delay_seconds=0.0,
        sheriff_sale_civilview_detail_limit=2,
    )
    source = CivilViewSheriffSource(settings, transport=httpx.MockTransport(_handler))
    records = await source.fetch()
    assert len(records) == 2


def test_phl_profile_still_uses_the_positional_parser() -> None:
    from lotscope.ingestion.loaders.sheriff_civilview import PHL_PROFILE, parse_sale_list

    assert PHL_PROFILE.parse_list is parse_sale_list
