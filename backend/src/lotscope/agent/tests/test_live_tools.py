"""The live tools, driven against a fake wire.

Every test here runs the real path — httpx request, response parse, diff, correction — with
only the transport faked, so a change to the SQL or the parser is caught rather than mocked
past.
"""

import json
from collections.abc import Iterator
from datetime import date
from typing import Any, cast

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.agent.tools import live_tools
from lotscope.agent.tools.live_tools import (
    SheriffInput,
    diff_fields,
    live_li_tool,
    live_opa_tool,
    live_rtt_tool,
    live_sheriff_tool,
)
from lotscope.agent.tools.read_tools import ParcelInput
from lotscope.agent.tools.registry import ToolContext

pytestmark = pytest.mark.integration

PARCEL = "phl:191357500"
ADDRESS = "3862 ASPEN ST"


class FakeRedis:
    """Enough Redis for the cache: get, set with a ttl, and nothing else."""

    # ToolContext wants a real Redis; the cache only ever calls get and set.

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.sets = 0

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.sets += 1
        self.store[key] = value


@pytest.fixture(autouse=True)
def _no_leaked_transport() -> Iterator[None]:
    yield
    live_tools.TRANSPORT = None


def carto(rows: list[dict[str, Any]]) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"rows": rows})

    return httpx.MockTransport(handle)


def timing_out() -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    return httpx.MockTransport(handle)


async def _user(session: AsyncSession, email: str) -> int:
    await session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
            "VALUES (:e, 'x', 'user', 'user', true)"
        ),
        {"e": email},
    )
    await session.flush()
    return int(await session.scalar(text("SELECT id FROM app_user WHERE email=:e"), {"e": email}))


async def _parcel(session: AsyncSession, *, owner: str = "OLD OWNER LLC") -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code, address, owner, mailing_address, "
            "land_use, market_value, is_vacant) VALUES (:p, 'phl', :a, :o, "
            "'1 MAIN ST PHILADELPHIA PA 19100', 'VACANT LAND', 40000, true)"
        ),
        {"p": PARCEL, "a": ADDRESS, "o": owner},
    )
    await session.flush()


async def _corrections(session: AsyncSession) -> int:
    return int(
        await session.scalar(
            text("SELECT count(*) FROM parcel_correction WHERE parcel_number = :p"), {"p": PARCEL}
        )
        or 0
    )


def _opa_row(owner: str) -> dict[str, Any]:
    return {
        "parcel_number": "191357500",
        "owner_1": owner,
        "mailing_address_1": "1 MAIN ST",
        "mailing_street": "",
        "mailing_city_state": "PHILADELPHIA PA",
        "mailing_zip": "19100",
        "market_value": 40000,
        "category_code_description": "VACANT LAND",
        "sale_date": "2019-04-02T00:00:00Z",
        "sale_price": 15000,
    }


# --- diff -------------------------------------------------------------------------------


def test_a_field_the_source_does_not_carry_is_silence_not_a_change() -> None:
    changes = diff_fields({"owner": None}, {"owner": "ACME LLC"})
    assert changes == []


def test_casing_and_spacing_are_not_a_change() -> None:
    assert diff_fields({"owner": "Acme  LLC"}, {"owner": "ACME LLC"}) == []


def test_a_real_change_is_reported_with_both_values() -> None:
    changes = diff_fields({"owner": "NEW LLC"}, {"owner": "ACME LLC"})
    assert changes == [{"field": "owner", "live": "NEW LLC", "stored": "ACME LLC"}]


# --- live_opa ---------------------------------------------------------------------------


async def test_live_opa_agreeing_reports_both_timestamps_and_files_nothing(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session, "opa-agree@example.com")
    await _parcel(db_session, owner="OLD OWNER LLC")
    live_tools.TRANSPORT = carto([_opa_row("OLD OWNER LLC")])

    result = await live_opa_tool(
        db_session, ToolContext(user_id=user_id), ParcelInput(parcel=ADDRESS)
    )

    assert result.data["diff"] == []
    assert result.data["correction_filed"] is None
    assert result.data["live_fetched_at"]
    assert "stored_ingested_at" in result.data
    assert any(source.name.endswith("(live)") and source.fetched_at for source in result.sources)
    assert await _corrections(db_session) == 0


async def test_live_opa_disagreeing_reports_the_live_owner_and_files_one_correction(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session, "opa-diff@example.com")
    await _parcel(db_session, owner="OLD OWNER LLC")
    live_tools.TRANSPORT = carto([_opa_row("NEW BUYER LLC")])

    result = await live_opa_tool(
        db_session, ToolContext(user_id=user_id), ParcelInput(parcel=PARCEL)
    )

    assert result.data["live"]["owner"] == "NEW BUYER LLC"
    assert result.data["stored"]["owner"] == "OLD OWNER LLC"
    assert [change["field"] for change in result.data["diff"]] == ["owner"]
    assert result.data["correction_filed"] is not None
    assert await _corrections(db_session) == 1


async def test_a_re_ask_within_the_cache_window_files_no_second_correction(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session, "opa-cache@example.com")
    await _parcel(db_session, owner="OLD OWNER LLC")
    live_tools.TRANSPORT = carto([_opa_row("NEW BUYER LLC")])
    redis = FakeRedis()
    context = ToolContext(user_id=user_id, redis=cast(Redis, redis))

    first = await live_opa_tool(db_session, context, ParcelInput(parcel=PARCEL))
    second = await live_opa_tool(db_session, context, ParcelInput(parcel=PARCEL))

    assert first.data["served_from_cache"] is False
    assert second.data["served_from_cache"] is True
    # The disagreement is still reported on the re-ask — only the filing is suppressed.
    assert second.data["diff"] == first.data["diff"]
    assert second.data["correction_filed"] is None
    assert await _corrections(db_session) == 1
    assert redis.sets == 1


async def test_live_opa_timing_out_returns_unverified_rather_than_raising(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session, "opa-timeout@example.com")
    await _parcel(db_session)
    live_tools.TRANSPORT = timing_out()

    result = await live_opa_tool(
        db_session, ToolContext(user_id=user_id), ParcelInput(parcel=PARCEL)
    )

    assert result.data["live"] is None
    assert result.data["stored"]["owner"] == "OLD OWNER LLC"
    assert any("did not come back" in note for note in result.unverified)
    assert await _corrections(db_session) == 0


# --- live_rtt ---------------------------------------------------------------------------


async def test_live_rtt_flags_a_deed_recorded_since_the_last_ingest(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session, "rtt-diff@example.com")
    await _parcel(db_session)
    await db_session.execute(
        text(
            "INSERT INTO sale (parcel_number, document_id, document_type, sale_date, sale_price, "
            "grantor, grantee) VALUES (:p, '5300111', 'DEED', '2019-04-02', 15000, 'A', 'B')"
        ),
        {"p": PARCEL},
    )
    await db_session.flush()
    live_tools.TRANSPORT = carto(
        [
            {
                "document_id": "5400999",
                "document_type": "DEED",
                "recording_date": "2026-08-30T00:00:00Z",
                "grantors": "B",
                "grantees": "NEW BUYER LLC",
                "total_consideration": 61000,
            }
        ]
    )

    result = await live_rtt_tool(
        db_session, ToolContext(user_id=user_id), ParcelInput(parcel=PARCEL)
    )

    assert [entry["document_id"] for entry in result.data["documents_not_in_lotscope"]] == [
        "5400999"
    ]
    assert result.data["diff"][0]["field"] == "latest_document_id"
    assert result.data["correction_filed"] is not None


async def test_live_rtt_timing_out_still_returns_the_stored_deeds_as_unverified(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session, "rtt-timeout@example.com")
    await _parcel(db_session)
    live_tools.TRANSPORT = timing_out()

    result = await live_rtt_tool(
        db_session, ToolContext(user_id=user_id), ParcelInput(parcel=PARCEL)
    )

    assert result.data["live"] is None
    assert any("did not come back" in note for note in result.unverified)


# --- live_li ----------------------------------------------------------------------------


async def test_live_li_counts_open_violations_and_files_the_gap(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, "li-diff@example.com")
    await _parcel(db_session)
    await db_session.execute(
        text(
            "INSERT INTO li_event (parcel_number, external_id, event_type, status, case_status, "
            "event_date) VALUES (:p, 'V1', 'violation', 'OPEN', 'IN VIOLATION', '2025-01-02')"
        ),
        {"p": PARCEL},
    )
    await db_session.flush()
    live_tools.TRANSPORT = carto(
        [
            {
                "violationnumber": "V1",
                "violationcodetitle": "TRASH",
                "violationstatus": "CLOSED",
                "casestatus": "CLOSED",
                "violationdate": "2025-01-02T00:00:00Z",
            }
        ]
    )

    result = await live_li_tool(
        db_session, ToolContext(user_id=user_id), ParcelInput(parcel=PARCEL)
    )

    assert result.data["stored"]["open_violations"] == 1
    assert result.data["live"]["open_violations"] == 0
    assert [change["field"] for change in result.data["diff"]] == ["open_violations"]
    assert result.data["correction_filed"] is not None


async def test_live_li_timing_out_reports_unverified(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, "li-timeout@example.com")
    await _parcel(db_session)
    live_tools.TRANSPORT = timing_out()

    result = await live_li_tool(
        db_session, ToolContext(user_id=user_id), ParcelInput(parcel=PARCEL)
    )

    assert result.data["live"] is None
    assert any("did not come back" in note for note in result.unverified)


# --- live_sheriff -----------------------------------------------------------------------

_LIST_HTML = """
<table><tr>
  <td><a href="/Sales/SaleDetails?PropertyId=99">Details</a></td>
  <td>2301-1234</td><td>191357500</td><td>3862 ASPEN ST</td><td>BANK NA</td>
</tr></table>
"""

_DETAIL_HTML = """
<div class="sale-detail-item">
  <span class="sale-detail-label">Sales Date:</span>
  <span class="sale-detail-value">10/07/2026</span>
</div>
<div class="sale-detail-item">
  <span class="sale-detail-label">Minimum Bid:</span>
  <span class="sale-detail-value">$1,500.00</span>
</div>
<table><tr><td>Postponed</td><td>09/02/2026</td></tr></table>
"""


def civilview(list_html: str = _LIST_HTML, detail_html: str = _DETAIL_HTML) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        body = detail_html if "SaleDetails" in request.url.path else list_html
        return httpx.Response(200, text=body)

    return httpx.MockTransport(handle)


async def _sheriff_row(session: AsyncSession, *, status: str, sale_date: str) -> None:
    await session.execute(
        text(
            "INSERT INTO sheriff_sale (parcel_number, case_number, status, sale_date) "
            "VALUES (:p, '2301-1234', :s, :d)"
        ),
        {"p": PARCEL, "s": status, "d": date.fromisoformat(sale_date)},
    )
    await session.flush()


async def test_live_sheriff_reports_a_postponement_our_copy_missed(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session, "sheriff-diff@example.com")
    await _parcel(db_session)
    await _sheriff_row(db_session, status="Active", sale_date="2026-09-02")
    live_tools.TRANSPORT = civilview()

    result = await live_sheriff_tool(
        db_session, ToolContext(user_id=user_id), SheriffInput(reference="2301-1234")
    )

    assert result.data["live"] == {"status": "Postponed", "sale_date": "2026-10-07"}
    assert result.data["stored"]["status"] == "Active"
    assert {change["field"] for change in result.data["diff"]} == {"status", "sale_date"}
    assert result.data["correction_filed"] is not None
    assert await _corrections(db_session) == 1


async def test_a_listing_absent_from_the_sale_list_is_not_reported_as_withdrawn(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session, "sheriff-absent@example.com")
    await _parcel(db_session)
    await _sheriff_row(db_session, status="Active", sale_date="2026-09-02")
    live_tools.TRANSPORT = civilview(list_html="<table></table>")

    result = await live_sheriff_tool(
        db_session, ToolContext(user_id=user_id), SheriffInput(reference="2301-1234")
    )

    assert result.data["live"] is None
    assert any("not scheduled right now" in note for note in result.unverified)
    assert await _corrections(db_session) == 0


async def test_live_sheriff_timing_out_reports_unverified(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, "sheriff-timeout@example.com")
    await _parcel(db_session)
    await _sheriff_row(db_session, status="Active", sale_date="2026-09-02")
    live_tools.TRANSPORT = timing_out()

    result = await live_sheriff_tool(
        db_session, ToolContext(user_id=user_id), SheriffInput(reference="2301-1234")
    )

    assert result.data["live"] is None
    assert result.data["stored"]["status"] == "Active"
    assert any("did not come back" in note for note in result.unverified)


# --- cache ------------------------------------------------------------------------------


async def test_a_broken_cache_entry_is_read_live_rather_than_failing(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session, "cache-corrupt@example.com")
    await _parcel(db_session)
    redis = FakeRedis()
    redis.store["live:live_opa:phl:191357500"] = "{not json"
    live_tools.TRANSPORT = carto([_opa_row("OLD OWNER LLC")])

    result = await live_opa_tool(
        db_session,
        ToolContext(user_id=user_id, redis=cast(Redis, redis)),
        ParcelInput(parcel=PARCEL),
    )

    assert result.data["served_from_cache"] is False
    assert json.loads(redis.store["live:live_opa:phl:191357500"])["payload"]
