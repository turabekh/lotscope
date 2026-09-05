"""Tools that read the primary source while the buyer waits.

The nightly ingest is an index, not the truth. Owner, last sale, open violations and sale
status are the four facts a buyer checks before they bid, so each of these tools reads the
source itself, puts the live value beside our stored one, and says when each was read.

When the two disagree the live value wins and a `parcel_correction` row is filed, so the
disagreement reaches a human instead of dying in a chat log. Corrections are filed only on a
genuine wire read: a cached repeat of the same question must not file a second row.
"""

from datetime import date, datetime
from typing import Any

import httpx
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.agent.envelope import Source, ToolResult, empty
from lotscope.agent.live.cache import CachedFetch, cached_fetch
from lotscope.agent.live.sources import (
    LiveFetchError,
    fetch_li,
    fetch_opa,
    fetch_rtt,
    fetch_sheriff,
)
from lotscope.agent.tools import urls
from lotscope.agent.tools.read_tools import ParcelInput, _fetched, _resolve
from lotscope.agent.tools.registry import ToolContext, tool
from lotscope.core.config import get_settings
from lotscope.core.market import MARKET_CODE
from lotscope.corrections.schemas import CorrectionCreate, CorrectionSection
from lotscope.corrections.service import report_correction
from lotscope.risk.violation_status import is_open_violation

# Tests point this at an httpx.MockTransport so the whole live path — request, parse, diff,
# correction — runs for real against a fake wire. None everywhere else.
TRANSPORT: httpx.AsyncBaseTransport | None = None

_MAX_FIELD_NAME = 60
_MAX_DESCRIPTION = 4000

_OPEN_CORRECTION_SQL = text(
    "SELECT 1 FROM parcel_correction "
    "WHERE parcel_number = :parcel AND field_name = :field AND status IN ('open', 'triaged') "
    "LIMIT 1"
)


class SheriffInput(BaseModel):
    reference: str = Field(
        description=(
            "A sheriff case number such as 2301-1234, a parcel number such as phl:191357500, "
            "or a Philadelphia street address."
        )
    )


def _norm(value: Any) -> str | None:
    """Compare on shape, not spelling, so casing and padding do not read as a change."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return str(value).casefold()
    if isinstance(value, int | float):
        # 24300 and 24300.0 are the same money.
        return f"{float(value):.2f}"
    cleaned = " ".join(str(value).split()).casefold()
    return cleaned or None


def _iso_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    raw = str(value).strip()
    if not raw:
        return None
    return raw[:10]


def diff_fields(live: dict[str, Any], stored: dict[str, Any]) -> list[dict[str, Any]]:
    """Fields present in both readings whose values do not match.

    A field the live source does not carry is silence, not a change, so it is skipped: an
    absent value must never be reported as the source having cleared ours.
    """
    changes: list[dict[str, Any]] = []
    for field_name, live_value in live.items():
        if live_value is None:
            continue
        stored_value = stored.get(field_name)
        if _norm(live_value) != _norm(stored_value):
            changes.append({"field": field_name, "live": live_value, "stored": stored_value})
    return changes


def _describe(parcel: str, source: str, changes: list[dict[str, Any]]) -> str:
    lines = [
        f"Filed by the analyst. A live read of {source} disagrees with LotScope's copy of {parcel}:"
    ]
    for change in changes:
        lines.append(f"- {change['field']}: live {change['live']!r}, stored {change['stored']!r}")
    lines.append("The live value was reported to the buyer. The stored value needs a re-ingest.")
    return "\n".join(lines)[:_MAX_DESCRIPTION]


async def _file_correction(
    session: AsyncSession,
    context: ToolContext,
    *,
    parcel_number: str,
    section: CorrectionSection,
    source: str,
    changes: list[dict[str, Any]],
) -> int | None:
    """One row per disagreement, or none if an identical one is already waiting on a human."""
    if not changes:
        return None

    field_name = ", ".join(change["field"] for change in changes)[:_MAX_FIELD_NAME]
    already_open = await session.scalar(
        _OPEN_CORRECTION_SQL, {"parcel": parcel_number, "field": field_name}
    )
    if already_open:
        return None

    correction = await report_correction(
        session,
        parcel_number=parcel_number,
        market_code=MARKET_CODE,
        reported_by=context.user_id,
        request=CorrectionCreate(
            section=section,
            field_name=field_name,
            description=_describe(parcel_number, source, changes),
        ),
        verdict=None,
    )
    return correction.id


async def _live(
    context: ToolContext, *, tool_name: str, argument: str, fetch: Any
) -> CachedFetch | str:
    """Run a live read, or return the reason it could not be made."""
    settings = get_settings()
    try:
        return await cached_fetch(
            context.redis,
            settings,
            tool=tool_name,
            argument=argument,
            fetch=lambda: fetch(settings, argument, transport=TRANSPORT),
        )
    except LiveFetchError as cause:
        return str(cause)


def _live_source(name: str, url: str | None, fetched_at: datetime) -> Source:
    return Source(name=f"{name} (live)", url=url, fetched_at=fetched_at)


def _stored_source(name: str, url: str, ingested: dict[str, datetime], dataset: str) -> Source:
    return Source(name=name, url=url, ingested_at=ingested.get(dataset))


def _timestamps(result: CachedFetch, ingested: datetime | None) -> dict[str, Any]:
    return {
        "live_fetched_at": result.fetched_at.isoformat(),
        "stored_ingested_at": ingested.isoformat() if ingested else None,
        "served_from_cache": result.from_cache,
    }


@tool(
    name="live_opa",
    description=(
        "Read the city assessment record for one parcel from OPA right now, and put it beside "
        "what LotScope stored: owner, mailing address, market value, land use, and OPA's own "
        "last sale date and price. Call this before you state an owner or a mailing address — "
        "a deed recorded since the last ingest is exactly the thing our copy will miss. The "
        "result carries a diff list; when it is not empty, the live value is the true one."
    ),
    input_model=ParcelInput,
)
async def live_opa_tool(
    session: AsyncSession, context: ToolContext, payload: ParcelInput
) -> ToolResult:
    row = await _resolve(session, payload.parcel)
    if row is None:
        return empty(f"No Philadelphia parcel matches {payload.parcel!r}.")

    result = await _live(context, tool_name="live_opa", argument=row.parcel_number, fetch=fetch_opa)
    ingested = (await _fetched(session)).get("opa_properties_public")

    stored_row = (
        (
            await session.execute(
                text(
                    "SELECT owner, mailing_address, market_value, land_use FROM parcel "
                    "WHERE parcel_number = :p"
                ),
                {"p": row.parcel_number},
            )
        )
        .mappings()
        .one()
    )
    stored = {
        "owner": stored_row["owner"],
        "mailing_address": stored_row["mailing_address"],
        "market_value": float(stored_row["market_value"])
        if stored_row["market_value"] is not None
        else None,
        "land_use": stored_row["land_use"],
    }

    if isinstance(result, str):
        return ToolResult(
            data={"parcel_number": row.parcel_number, "stored": stored, "live": None},
            sources=[_stored_source("parcel", urls.OPA_URL, {}, "opa_properties_public")],
            unverified=[
                f"The live OPA read did not come back ({result}). Everything below is "
                f"LotScope's stored copy, last ingested "
                f"{ingested.isoformat() if ingested else 'at an unknown time'}."
            ],
        )

    live_row = result.payload.get("row")
    if live_row is None:
        return ToolResult(
            data={
                "parcel_number": row.parcel_number,
                "stored": stored,
                "live": None,
                **_timestamps(result, ingested),
            },
            sources=[
                _live_source("opa_properties_public", result.payload.get("url"), result.fetched_at)
            ],
            unverified=[f"OPA has no row for {row.parcel_number} today."],
        )

    mailing = " ".join(
        part
        for part in (
            live_row.get("mailing_address_1"),
            live_row.get("mailing_street"),
            live_row.get("mailing_city_state"),
            live_row.get("mailing_zip"),
        )
        if part
    )
    live = {
        "owner": live_row.get("owner_1"),
        "mailing_address": mailing or None,
        "market_value": live_row.get("market_value"),
        "land_use": live_row.get("category_code_description"),
    }
    changes = diff_fields(live, stored)
    correction_id = (
        await _file_correction(
            session,
            context,
            parcel_number=row.parcel_number,
            section="ownership",
            source="OPA",
            changes=changes,
        )
        if not result.from_cache
        else None
    )

    return ToolResult(
        data={
            "parcel_number": row.parcel_number,
            "live": live,
            "stored": stored,
            "diff": changes,
            "opa_last_sale": {
                "sale_date": _iso_date(live_row.get("sale_date")),
                "sale_price": live_row.get("sale_price"),
            },
            "correction_filed": correction_id,
            **_timestamps(result, ingested),
        },
        sources=[
            _live_source("opa_properties_public", result.payload.get("url"), result.fetched_at),
            Source(name="parcel", url=urls.OPA_URL, ingested_at=ingested),
            Source(name="atlas", url=urls.atlas(row.parcel_number)),
        ],
        unverified=[
            "OPA's sale_date and sale_price are the assessment record's own last-sale fields, "
            "not the deed index. Use live_rtt for the recorded deed; the two can differ "
            "legitimately, so a difference between them is not an error."
        ],
    )


@tool(
    name="live_rtt",
    description=(
        "Read the last five recorded documents for one parcel from the Department of Records "
        "transfer index right now, and compare them with the deeds LotScope stored. Call this "
        "before you state who bought a lot, when, or for how much. Any live document id absent "
        "from our copy is a transfer recorded since the last ingest."
    ),
    input_model=ParcelInput,
)
async def live_rtt_tool(
    session: AsyncSession, context: ToolContext, payload: ParcelInput
) -> ToolResult:
    row = await _resolve(session, payload.parcel)
    if row is None:
        return empty(f"No Philadelphia parcel matches {payload.parcel!r}.")

    result = await _live(context, tool_name="live_rtt", argument=row.parcel_number, fetch=fetch_rtt)
    ingested = (await _fetched(session)).get("rtt_summary")

    stored_rows = (
        (
            await session.execute(
                text(
                    "SELECT document_id, document_type, sale_date, sale_price, grantor, grantee "
                    "FROM sale WHERE parcel_number = :p "
                    "ORDER BY sale_date DESC NULLS LAST LIMIT 5"
                ),
                {"p": row.parcel_number},
            )
        )
        .mappings()
        .all()
    )
    stored = [
        {
            "document_id": entry["document_id"],
            "document_type": entry["document_type"],
            "recording_date": _iso_date(entry["sale_date"]),
            "grantee": entry["grantee"],
            "consideration": (
                float(entry["sale_price"]) if entry["sale_price"] is not None else None
            ),
        }
        for entry in stored_rows
    ]

    if isinstance(result, str):
        return ToolResult(
            data={"parcel_number": row.parcel_number, "stored": stored, "live": None},
            sources=[Source(name="sale", url=urls.RTT_URL, ingested_at=ingested)],
            unverified=[f"The live transfer-index read did not come back ({result})."],
        )

    live = [
        {
            "document_id": str(entry.get("document_id")) if entry.get("document_id") else None,
            "document_type": entry.get("document_type"),
            "recording_date": _iso_date(entry.get("recording_date")),
            "grantor": entry.get("grantors"),
            "grantee": entry.get("grantees"),
            "consideration": entry.get("total_consideration"),
        }
        for entry in result.payload.get("rows", [])
    ]

    known = {str(entry["document_id"]) for entry in stored if entry["document_id"]}
    unseen = [entry for entry in live if entry["document_id"] and entry["document_id"] not in known]
    changes = (
        [
            {
                "field": "latest_document_id",
                "live": live[0]["document_id"],
                "stored": stored[0]["document_id"] if stored else None,
            }
        ]
        if unseen and live
        else []
    )
    correction_id = (
        await _file_correction(
            session,
            context,
            parcel_number=row.parcel_number,
            section="ownership",
            source="the transfer index",
            changes=changes,
        )
        if not result.from_cache
        else None
    )

    return ToolResult(
        data={
            "parcel_number": row.parcel_number,
            "live": live,
            "stored": stored,
            "documents_not_in_lotscope": unseen,
            "diff": changes,
            "correction_filed": correction_id,
            **_timestamps(result, ingested),
        },
        sources=[
            _live_source("rtt_summary", result.payload.get("url"), result.fetched_at),
            Source(name="sale", url=urls.RTT_URL, ingested_at=ingested),
        ],
        unverified=[
            "The transfer index records what was recorded. A deed signed and not yet recorded "
            "is invisible here."
        ],
    )


@tool(
    name="live_li",
    description=(
        "Read Licences and Inspections violations for one parcel right now and compare the open "
        "count with LotScope's. Call this before you state how many violations are open — a "
        "case closed or opened since the last ingest is exactly what our copy will miss. This "
        "reads the violations table, which carries the case status on each violation row."
    ),
    input_model=ParcelInput,
)
async def live_li_tool(
    session: AsyncSession, context: ToolContext, payload: ParcelInput
) -> ToolResult:
    row = await _resolve(session, payload.parcel)
    if row is None:
        return empty(f"No Philadelphia parcel matches {payload.parcel!r}.")

    result = await _live(context, tool_name="live_li", argument=row.parcel_number, fetch=fetch_li)
    ingested = (await _fetched(session)).get("violations")

    stored_rows = (
        (
            await session.execute(
                text(
                    "SELECT status, case_status, event_date, description FROM li_event "
                    "WHERE parcel_number = :p AND event_type = 'violation'"
                ),
                {"p": row.parcel_number},
            )
        )
        .mappings()
        .all()
    )
    stored = {
        "violations_on_record": len(stored_rows),
        "open_violations": sum(
            1 for entry in stored_rows if is_open_violation(entry["status"], entry["case_status"])
        ),
    }

    if isinstance(result, str):
        return ToolResult(
            data={"parcel_number": row.parcel_number, "stored": stored, "live": None},
            sources=[Source(name="li_event", url=urls.LI_URL, ingested_at=ingested)],
            unverified=[f"The live L&I read did not come back ({result})."],
        )

    live_rows = result.payload.get("rows", [])
    open_rows = [
        entry
        for entry in live_rows
        if is_open_violation(entry.get("violationstatus"), entry.get("casestatus"))
    ]
    live = {"violations_on_record": len(live_rows), "open_violations": len(open_rows)}
    changes = diff_fields(live, stored)
    correction_id = (
        await _file_correction(
            session,
            context,
            parcel_number=row.parcel_number,
            section="risk",
            source="L&I",
            changes=changes,
        )
        if not result.from_cache
        else None
    )

    return ToolResult(
        data={
            "parcel_number": row.parcel_number,
            "live": live,
            "stored": stored,
            "diff": changes,
            "open_violations_detail": [
                {
                    "violation_number": entry.get("violationnumber"),
                    "title": entry.get("violationcodetitle"),
                    "status": entry.get("violationstatus"),
                    "case_status": entry.get("casestatus"),
                    "violation_date": _iso_date(entry.get("violationdate")),
                }
                for entry in open_rows[:25]
            ],
            "correction_filed": correction_id,
            **_timestamps(result, ingested),
        },
        sources=[
            _live_source("violations", result.payload.get("url"), result.fetched_at),
            Source(name="li_event", url=urls.LI_URL, ingested_at=ingested),
            Source(name="li_property_history", url=urls.li_history(row.address)),
        ],
        unverified=[
            "L&I records what was reported and inspected. An unreported condition is invisible "
            "here, live or stored."
        ],
    )


@tool(
    name="live_sheriff",
    description=(
        "Read one listing off the sheriff's public sale site right now — current status and "
        "sale date — and compare it with LotScope's copy. Call this before you tell a buyer a "
        "lot is still selling, or on what date. Listings are postponed, stayed and withdrawn "
        "between nightly reads, and a buyer standing at an auction pays for that gap."
    ),
    input_model=SheriffInput,
)
async def live_sheriff_tool(
    session: AsyncSession, context: ToolContext, payload: SheriffInput
) -> ToolResult:
    stored_row = (
        (
            await session.execute(
                text(
                    "SELECT parcel_number, case_number, status, sale_date, sale_type, opening_bid "
                    "FROM sheriff_sale WHERE lower(case_number) = lower(:needle) "
                    "OR lower(parcel_number) = lower(:needle) "
                    "ORDER BY sale_date DESC NULLS LAST LIMIT 1"
                ),
                {"needle": payload.reference.strip()},
            )
        )
        .mappings()
        .one_or_none()
    )
    if stored_row is None:
        resolved = await _resolve(session, payload.reference)
        if resolved is not None:
            stored_row = (
                (
                    await session.execute(
                        text(
                            "SELECT parcel_number, case_number, status, sale_date, sale_type, "
                            "opening_bid FROM sheriff_sale WHERE parcel_number = :p "
                            "ORDER BY sale_date DESC NULLS LAST LIMIT 1"
                        ),
                        {"p": resolved.parcel_number},
                    )
                )
                .mappings()
                .one_or_none()
            )

    lookup = stored_row["case_number"] if stored_row else payload.reference.strip()
    result = await _live(context, tool_name="live_sheriff", argument=lookup, fetch=fetch_sheriff)
    ingested = (await _fetched(session)).get("sheriff_sale")

    stored = (
        {
            "case_number": stored_row["case_number"],
            "status": stored_row["status"],
            "sale_date": _iso_date(stored_row["sale_date"]),
        }
        if stored_row
        else {"case_number": None, "status": None, "sale_date": None}
    )

    if isinstance(result, str):
        return ToolResult(
            data={"stored": stored, "live": None},
            sources=[Source(name="sheriff_sale", url=urls.CIVILVIEW, ingested_at=ingested)],
            unverified=[f"The live sheriff read did not come back ({result})."],
        )

    if not result.payload.get("listed"):
        return ToolResult(
            data={"stored": stored, "live": None, **_timestamps(result, ingested)},
            sources=[_live_source("civilview", result.payload.get("url"), result.fetched_at)],
            unverified=[
                f"{payload.reference} is not on the sheriff's current sale list. That means it "
                "is not scheduled right now; it does not mean it never was."
            ],
        )

    detail = result.payload.get("detail") or {}
    live = {"status": detail.get("status"), "sale_date": _iso_date(detail.get("sale_date"))}
    changes = diff_fields(live, stored)
    correction_id = (
        await _file_correction(
            session,
            context,
            parcel_number=stored_row["parcel_number"] if stored_row else payload.reference.strip(),
            section="risk",
            source="the sheriff's sale site",
            changes=changes,
        )
        if not result.from_cache and stored_row is not None
        else None
    )

    return ToolResult(
        data={
            "case_number": result.payload.get("case_number") or stored["case_number"],
            "address": result.payload.get("address"),
            "live": live,
            "stored": stored,
            "diff": changes,
            "opening_bid": detail.get("opening_bid"),
            "correction_filed": correction_id,
            **_timestamps(result, ingested),
        },
        sources=[
            _live_source("civilview", result.payload.get("url"), result.fetched_at),
            Source(name="sheriff_sale", url=urls.CIVILVIEW, ingested_at=ingested),
        ],
        unverified=[
            "The opening bid on this page is a nominal minimum, not a price. Water and gas "
            "liens are not on it."
        ],
    )
