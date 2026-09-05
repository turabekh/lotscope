"""Live verification inside the packet, against a fake wire."""

from datetime import UTC, date, datetime
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.agent.tools import live_tools
from lotscope.packet.live_verify import VERIFIED_VERDICTS, verify_lots
from lotscope.packet.schemas import PacketLot

pytestmark = pytest.mark.integration

PARCEL = "phl:191357500"
ADDRESS = "3862 ASPEN ST"
CASE = "2301-1234"

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
<table><tr><td>Postponed</td><td>09/02/2026</td></tr></table>
"""


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value


def _transport(violations: list[dict[str, Any]]) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        if "civilview" in str(request.url) or "Sales" in request.url.path:
            body = _DETAIL_HTML if "SaleDetails" in request.url.path else _LIST_HTML
            return httpx.Response(200, text=body)
        return httpx.Response(200, json={"rows": violations})

    return httpx.MockTransport(handle)


@pytest.fixture(autouse=True)
def _clear_transport() -> Any:
    yield
    live_tools.TRANSPORT = None


async def _user(session: AsyncSession, email: str) -> int:
    return int(
        await session.scalar(
            text(
                "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
                "VALUES (:e, 'x', 'user', 'user', true) RETURNING id"
            ),
            {"e": email},
        )
    )


async def _fixtures(session: AsyncSession) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code, address, owner, is_vacant) "
            "VALUES (:p, 'phl', :a, 'ACME LLC', true)"
        ),
        {"p": PARCEL, "a": ADDRESS},
    )
    await session.execute(
        text(
            "INSERT INTO li_event (parcel_number, external_id, event_type, status, "
            "case_status, event_date) VALUES (:p, 'VI-1', 'violation', 'OPEN', "
            "'IN VIOLATION', '2025-01-02')"
        ),
        {"p": PARCEL},
    )
    await session.execute(
        text(
            "INSERT INTO sheriff_sale (parcel_number, case_number, status, sale_date) "
            "VALUES (:p, :c, 'Active', :d)"
        ),
        {"p": PARCEL, "c": CASE, "d": date(2026, 9, 2)},
    )
    await session.flush()


def _lot(verdict: str) -> PacketLot:
    return PacketLot(
        parcel_number=PARCEL,
        address=ADDRESS,
        case_number=CASE,
        is_scheduled=True,
        is_vacant=True,
        verdict=verdict,
        verdict_reason="fixture",
        graded_as="build",
        grade_rule="fixture",
        computed_at=datetime.now(UTC),
    )


async def _corrections(session: AsyncSession) -> int:
    return int(
        await session.scalar(
            text("SELECT count(*) FROM parcel_correction WHERE parcel_number = :p"), {"p": PARCEL}
        )
        or 0
    )


async def test_a_bid_lot_with_a_diff_gets_the_line_and_one_correction(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session, "packet-live-diff@example.com")
    await _fixtures(db_session)
    # The violation we hold has been closed, and the sale has been postponed.
    live_tools.TRANSPORT = _transport(
        [
            {
                "violationnumber": "VI-1",
                "violationcodetitle": "TRASH",
                "violationstatus": "CLOSED",
                "casestatus": "CLOSED",
                "violationdate": "2025-01-02T00:00:00Z",
            }
        ]
    )
    lot = _lot("BID")

    disagreed = await verify_lots(db_session, [lot], user_id=user_id)

    assert disagreed == 1
    assert [check.field for check in lot.live_checks] == ["open_violations", "sale_status"]

    violations, sale = lot.live_checks
    assert violations.agrees is False
    assert violations.stored == "1"
    assert violations.live == "0"
    assert violations.fetched_at is not None

    assert sale.agrees is False
    assert "Postponed on 2026-10-07" in (sale.live or "")
    assert "Active on 2026-09-02" in (sale.stored or "")

    # One row per disagreeing source, not one per lot.
    assert await _corrections(db_session) == 2


async def test_a_re_run_inside_the_cache_window_files_nothing_further(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session, "packet-live-cache@example.com")
    await _fixtures(db_session)
    live_tools.TRANSPORT = _transport(
        [
            {
                "violationnumber": "VI-1",
                "violationcodetitle": "TRASH",
                "violationstatus": "CLOSED",
                "casestatus": "CLOSED",
                "violationdate": "2025-01-02T00:00:00Z",
            }
        ]
    )
    redis: Any = FakeRedis()

    first = _lot("BID")
    await verify_lots(db_session, [first], user_id=user_id, redis=redis)
    after_first = await _corrections(db_session)

    second = _lot("BID")
    disagreed = await verify_lots(db_session, [second], user_id=user_id, redis=redis)

    assert after_first == 2
    # The disagreement is still reported on the reprint — only the filing is suppressed.
    assert disagreed == 1
    assert [check.agrees for check in second.live_checks] == [False, False]
    assert all(check.correction_id is None for check in second.live_checks)
    assert await _corrections(db_session) == 2


async def test_a_pass_lot_is_left_on_the_index(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, "packet-live-pass@example.com")
    await _fixtures(db_session)
    live_tools.TRANSPORT = _transport([])
    lot = _lot("PASS")

    disagreed = await verify_lots(db_session, [lot], user_id=user_id)

    assert disagreed == 0
    assert lot.live_checks == []
    assert await _corrections(db_session) == 0


def test_only_bid_and_look_lots_are_verified() -> None:
    assert VERIFIED_VERDICTS == ("BID", "LOOK")


async def test_a_source_that_does_not_answer_is_marked_unverified_not_agreed(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session, "packet-live-down@example.com")
    await _fixtures(db_session)

    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    live_tools.TRANSPORT = httpx.MockTransport(handle)
    lot = _lot("LOOK")

    disagreed = await verify_lots(db_session, [lot], user_id=user_id)

    assert disagreed == 1
    assert all(check.live is None for check in lot.live_checks)
    assert all("unverified" in check.note for check in lot.live_checks)
    assert await _corrections(db_session) == 0
