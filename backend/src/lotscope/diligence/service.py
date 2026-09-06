"""The pre-closing checklist on one parcel.

Every line is built from the same tools the Analyst uses, so a buyer who asks a question
in the conversation and a buyer who buys the report get the same answer from the same
read. What a buyer will check themselves — the deed chain, open cases, the sale listing —
is read live at the moment the report is made; the rest is our copy, and each line says
which it is.

Nothing here is allowed to go quiet. A check we cannot run reads "unverified" and names
where the buyer should go instead, because a checklist that silently omits a line is one
the buyer will assume is clear.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.agent.envelope import Source, ToolResult
from lotscope.agent.tools import REGISTRY
from lotscope.agent.tools.registry import ToolContext
from lotscope.core.config import get_settings
from lotscope.core.errors import NotFoundError
from lotscope.core.logging import get_logger
from lotscope.diligence.models import DiligenceRun
from lotscope.diligence.render import diligence_filename, render_diligence_pdf
from lotscope.diligence.schemas import (
    CHECK_KEYS,
    CheckStatus,
    DiligenceLine,
    DiligenceReport,
)
from lotscope.risk.party_match import match_parties

_logger = get_logger("diligence.service")

_PARCEL_SQL = text(
    "SELECT parcel_number, address, owner FROM parcel WHERE parcel_number = :parcel_number"
)

# An unsafe or imminently dangerous structure next door is the neighbour's problem until
# it falls on this lot, so it is a flag on this report rather than a footnote on theirs.
_ADJACENT_UNSAFE_SQL = text(
    "SELECT p.parcel_number, p.address, "
    "  bool_or(e.is_imminently_dangerous) AS imminently_dangerous "
    "FROM parcel subject "
    "JOIN parcel p ON p.parcel_number <> subject.parcel_number "
    "  AND ST_Touches(p.geom_local, subject.geom_local) "
    "JOIN li_event e ON e.parcel_number = p.parcel_number "
    "WHERE subject.parcel_number = :parcel_number "
    "  AND (e.is_unsafe OR e.is_imminently_dangerous) "
    "  AND coalesce(upper(e.case_status), '') <> 'CLOSED' "
    "GROUP BY p.parcel_number, p.address ORDER BY p.parcel_number"
)

# A shared boundary with a built neighbour is where a party wall lives. We can see the
# boundary in PWD's geometry; whether the wall is party or independent is a survey.
_SHARED_BOUNDARY_SQL = text(
    "SELECT p.parcel_number, p.address, coalesce(p.is_vacant, false) AS is_vacant, "
    "  round(ST_Length(ST_Intersection(p.geom_local, subject.geom_local))::numeric, 1) "
    "    AS shared_ft "
    "FROM parcel subject "
    "JOIN parcel p ON p.parcel_number <> subject.parcel_number "
    "  AND ST_Touches(p.geom_local, subject.geom_local) "
    "WHERE subject.parcel_number = :parcel_number "
    "ORDER BY shared_ft DESC NULLS LAST"
)

_GRANTOR_SQL = text(
    "SELECT sale_date, document_type, grantor, grantee FROM sale "
    "WHERE parcel_number = :parcel_number ORDER BY sale_date DESC NULLS LAST LIMIT 25"
)

# Words a Philadelphia deed uses when the seller is a decedent's estate rather than a
# person. They are what turns a transfer into a probate question at closing.
_ESTATE_MARKERS = (
    "ESTATE OF",
    "EXECUTOR",
    "EXECUTRIX",
    "ADMINISTRATOR",
    "ADMINISTRATRIX",
    "DECEASED",
    "HEIRS",
    "PERSONAL REPRESENTATIVE",
    "TRUSTEE UNDER WILL",
)

_LABELS: dict[str, str] = {
    "title_chain": "Title chain",
    "delinquency": "Tax delinquency and the named debtor",
    "li_open_cases": "L&I open cases",
    "adjacent_unsafe": "Unsafe structures next door",
    "conservatorship": "Act 135 conservatorship",
    "historic": "Historic designation",
    "overlays_rco": "Overlays and registered community organisations",
    "flood": "Flood hazard area",
    "public_neighbour": "Public-owner adjacency and Land Bank disposition",
    "estate_probate": "Estate and probate signals in the deed parties",
    "party_wall": "Party walls and shared boundaries",
    "utilities_curb": "Utilities and curb cut",
    "sheriff": "Sheriff-sale listing",
}


def _money(value: object) -> str:
    """A figure a buyer will read as money, or a phrase saying we do not have one."""
    if value is None:
        return "an unrecorded amount"
    try:
        return f"${float(str(value)):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def _stamp(sources: list[Source], name: str | None = None) -> tuple[str, str | None, Any, Any]:
    """The first source of a tool result, as a line's provenance."""
    for source in sources:
        if name is None or source.name == name:
            return source.name, source.url, source.fetched_at, source.ingested_at
    if sources:
        first = sources[0]
        return first.name, first.url, first.fetched_at, first.ingested_at
    return "lotscope", None, None, None


def _line(
    key: str,
    status: CheckStatus,
    evidence: str,
    *,
    source: str,
    source_url: str | None = None,
    fetched_at: datetime | None = None,
    ingested_at: datetime | None = None,
) -> DiligenceLine:
    return DiligenceLine(
        key=key,
        label=_LABELS[key],
        status=status,
        evidence=evidence,
        source=source,
        source_url=source_url,
        fetched_at=fetched_at,
        ingested_at=ingested_at,
    )


async def _run_tool(
    session: AsyncSession, context: ToolContext, name: str, parcel_number: str
) -> ToolResult | None:
    """One of the Analyst's tools, or None if it could not run.

    A tool that raises is a check we could not make, which the line says. It is never a
    reason to drop the line or to answer from something else.
    """
    registered = REGISTRY.get(name)
    if registered is None:  # pragma: no cover - the registry is imported at module load
        return None
    try:
        payload = registered.input_model.model_validate({"parcel": parcel_number})
        return await registered.handler(session, context, payload)
    except Exception as error:
        _logger.warning(
            "diligence_check_failed", check=name, parcel=parcel_number, error=str(error)
        )
        return None


def _title_chain_line(result: ToolResult | None) -> DiligenceLine:
    if result is None:
        return _line(
            "title_chain",
            "unverified",
            "The recorder could not be read at the time of this report, so the chain of "
            "title has not been checked.",
            source="rtt_summary",
        )
    source, url, fetched_at, ingested_at = _stamp(result.sources)
    never_stored = result.data.get("never_stored") or []
    recorded_since = result.data.get("recorded_since_our_last_read") or []
    deeds = result.data.get("deeds") or result.data.get("live") or []
    if recorded_since:
        return _line(
            "title_chain",
            "flag",
            f"{len(recorded_since)} transfer(s) recorded since our last read of the deed "
            "index. Read the newest deed before you rely on who owns this.",
            source=source,
            source_url=url,
            fetched_at=fetched_at,
            ingested_at=ingested_at,
        )
    if never_stored:
        return _line(
            "title_chain",
            "flag",
            f"{len(never_stored)} recorded transfer(s) the live index holds that our copy "
            "does not. They are historical, not new, but the chain we show is incomplete.",
            source=source,
            source_url=url,
            fetched_at=fetched_at,
            ingested_at=ingested_at,
        )
    count = len(deeds) if isinstance(deeds, list) else 0
    if count == 0:
        return _line(
            "title_chain",
            "unverified",
            "No recorded transfer is on file for this parcel, which is not the same as a "
            "clean chain — order a title search.",
            source=source,
            source_url=url,
            fetched_at=fetched_at,
            ingested_at=ingested_at,
        )
    return _line(
        "title_chain",
        "clear",
        f"The live deed index agrees with our copy across {count} recorded transfer(s); no "
        "gap and nothing recorded since we last read it.",
        source=source,
        source_url=url,
        fetched_at=fetched_at,
        ingested_at=ingested_at,
    )


def _delinquency_line(result: ToolResult | None, owner: str | None) -> DiligenceLine:
    if result is None:
        return _line(
            "delinquency",
            "unverified",
            "The tax record could not be read for this report.",
            source="tax_status",
        )
    source, url, fetched_at, ingested_at = _stamp(result.sources, "tax_status")
    tax = result.data.get("tax") or {}
    attribution = result.data.get("attribution")
    if not tax:
        return _line(
            "delinquency",
            "unverified",
            "No tax record is on file for this parcel, so delinquency is unconfirmed.",
            source=source,
            source_url=url,
            ingested_at=ingested_at,
            fetched_at=fetched_at,
        )
    if not tax.get("is_delinquent"):
        return _line(
            "delinquency",
            "clear",
            f"Not recorded as delinquent as of {tax.get('as_of_date') or 'an unrecorded date'}.",
            source=source,
            source_url=url,
            ingested_at=ingested_at,
            fetched_at=fetched_at,
        )
    debtor = tax.get("delinquency_owner") or "no name recorded"
    owed = _money(tax.get("total_due"))
    evidence = (
        f"Delinquent: {owed} recorded as due, against {debtor}"
        f"{'' if debtor == (owner or '') else f', not the current owner {owner or "unknown"}'}."
    )
    if attribution:
        evidence = f"{evidence} {attribution}"
    return _line(
        "delinquency",
        "flag",
        evidence,
        source=source,
        source_url=url,
        ingested_at=ingested_at,
        fetched_at=fetched_at,
    )


def _li_line(result: ToolResult | None) -> DiligenceLine:
    if result is None:
        return _line(
            "li_open_cases",
            "unverified",
            "L&I could not be read at the time of this report, so open cases are unchecked.",
            source="li_event",
        )
    source, url, fetched_at, ingested_at = _stamp(result.sources)
    live = result.data.get("live") or {}
    open_now = live.get("open_violations")
    if open_now is None:
        open_now = (result.data.get("posture") or {}).get("open_violations")
    on_record = live.get("violations_on_record")
    if open_now is None:
        return _line(
            "li_open_cases",
            "unverified",
            "L&I returned no count for this parcel.",
            source=source,
            source_url=url,
            fetched_at=fetched_at,
            ingested_at=ingested_at,
        )
    if int(open_now) == 0:
        return _line(
            "li_open_cases",
            "clear",
            f"No open L&I violation at the live read; {on_record or 0} on record. An "
            "unreported condition is invisible to L&I and so to this line.",
            source=source,
            source_url=url,
            fetched_at=fetched_at,
            ingested_at=ingested_at,
        )
    return _line(
        "li_open_cases",
        "flag",
        f"{int(open_now)} open L&I violation(s) at the live read, {on_record or 0} on "
        "record. Open cases pass to the buyer on settlement.",
        source=source,
        source_url=url,
        fetched_at=fetched_at,
        ingested_at=ingested_at,
    )


async def _adjacent_unsafe_line(session: AsyncSession, parcel_number: str) -> DiligenceLine:
    rows = (
        (await session.execute(_ADJACENT_UNSAFE_SQL, {"parcel_number": parcel_number}))
        .mappings()
        .all()
    )
    if not rows:
        return _line(
            "adjacent_unsafe",
            "clear",
            "No open unsafe or imminently dangerous case is recorded against a parcel "
            "sharing a boundary with this one.",
            source="li_event",
        )
    worst = "imminently dangerous" if any(r["imminently_dangerous"] for r in rows) else "unsafe"
    named = ", ".join(str(r["address"] or r["parcel_number"]) for r in rows[:3])
    return _line(
        "adjacent_unsafe",
        "flag",
        f"{len(rows)} adjoining parcel(s) carry an open {worst} case: {named}. A demolition "
        "next door is a party-wall and site-access question for this lot.",
        source="li_event",
    )


def _conservatorship_line() -> DiligenceLine:
    return _line(
        "conservatorship",
        "unverified",
        "Not in our data — check the Court of Common Pleas docket for an Act 135 "
        "conservatorship petition against this address.",
        source="none",
    )


def _overlays_line(result: ToolResult | None) -> tuple[DiligenceLine, DiligenceLine, DiligenceLine]:
    if result is None:
        unread = "The overlay, historic and flood layers could not be read for this report."
        return (
            _line("historic", "unverified", unread, source="historic_district"),
            _line("overlays_rco", "unverified", unread, source="zoning_overlay"),
            _line("flood", "unverified", unread, source="flood_zone"),
        )
    _, url, fetched_at, ingested_at = _stamp(result.sources)
    data = result.data
    historic = _line(
        "historic",
        "flag" if data.get("in_historic_district") else "clear",
        "In a designated historic district: exterior work needs Historical Commission review."
        if data.get("in_historic_district")
        else "Not in a designated historic district.",
        source="historic_district",
        source_url=url,
        ingested_at=ingested_at,
        fetched_at=fetched_at,
    )
    overlay_names = [
        str(overlay.get("name") or overlay.get("code"))
        for overlay in (data.get("overlays") or [])
        if isinstance(overlay, dict)
    ]
    rcos = [str(name) for name in (data.get("rcos") or [])]
    if overlay_names or rcos:
        parts = []
        if overlay_names:
            parts.append(f"overlays: {', '.join(overlay_names)}")
        if rcos:
            parts.append(f"RCOs to notify: {', '.join(rcos)}")
        overlays = _line(
            "overlays_rco",
            "flag",
            "; ".join(parts).capitalize()
            + ". An overlay can change what is buildable by right, and an RCO meeting is "
            "required before a variance hearing.",
            source="zoning_overlay",
            source_url=url,
            ingested_at=ingested_at,
        )
    else:
        overlays = _line(
            "overlays_rco",
            "clear",
            "No zoning overlay and no registered community organisation recorded over this parcel.",
            source="zoning_overlay",
            source_url=url,
            ingested_at=ingested_at,
        )
    flood = _line(
        "flood",
        "flag" if data.get("in_flood_hazard_area") else "clear",
        "Inside a FEMA special flood hazard area: insurance and elevation requirements apply."
        if data.get("in_flood_hazard_area")
        else "Not inside a FEMA special flood hazard area.",
        source="flood_zone",
        source_url=url,
        ingested_at=ingested_at,
    )
    return historic, overlays, flood


def _public_neighbour_line(result: ToolResult | None) -> DiligenceLine:
    if result is None:
        return _line(
            "public_neighbour",
            "unverified",
            "Adjacency could not be computed for this parcel.",
            source="pwd_parcel",
        )
    source, url, _fetched_at, ingested_at = _stamp(result.sources, "pwd_parcel")
    public = [
        neighbour
        for neighbour in (result.data.get("neighbors") or [])
        if neighbour.get("is_city_owned")
    ]
    if not public:
        return _line(
            "public_neighbour",
            "clear",
            "No publicly held parcel shares a boundary with this one.",
            source=source,
            source_url=url,
            ingested_at=ingested_at,
        )
    named = ", ".join(str(n.get("address") or n.get("parcel_number")) for n in public[:3])
    return _line(
        "public_neighbour",
        "flag",
        f"{len(public)} adjoining parcel(s) are publicly held: {named}. Whether the Land "
        "Bank has listed any of them for disposition is not in our data — ask the "
        "Philadelphia Land Bank for its disposition status before you plan an assemblage.",
        source=source,
        source_url=url,
        ingested_at=ingested_at,
    )


async def _estate_line(
    session: AsyncSession, parcel_number: str, owner: str | None
) -> DiligenceLine:
    rows = (await session.execute(_GRANTOR_SQL, {"parcel_number": parcel_number})).mappings().all()
    hits = [
        row
        for row in rows
        if any(marker in (row["grantor"] or "").upper() for marker in _ESTATE_MARKERS)
    ]
    if not hits:
        if not rows:
            return _line(
                "estate_probate",
                "unverified",
                "No recorded transfer carries party names, so probate signals cannot be read.",
                source="rtt_summary",
            )
        return _line(
            "estate_probate",
            "clear",
            f"No estate, executor or heirs language in the grantor names across "
            f"{len(rows)} recorded transfer(s).",
            source="rtt_summary",
        )
    newest = hits[0]
    match = match_parties(newest["grantee"], owner)
    same = " The grantee matches the current owner of record." if match.strength == "exact" else ""
    return _line(
        "estate_probate",
        "flag",
        f"A {newest['document_type'] or 'transfer'} dated "
        f"{newest['sale_date'] or 'an unrecorded date'} names {newest['grantor']} as "
        f"grantor — estate language, so the seller's authority came through probate.{same} "
        "Ask for the letters testamentary with the title search.",
        source="rtt_summary",
    )


async def _party_wall_line(session: AsyncSession, parcel_number: str) -> DiligenceLine:
    rows = (
        (await session.execute(_SHARED_BOUNDARY_SQL, {"parcel_number": parcel_number}))
        .mappings()
        .all()
    )
    built = [row for row in rows if not row["is_vacant"]]
    if not rows:
        return _line(
            "party_wall",
            "unverified",
            "No adjoining parcel geometry, so shared boundaries could not be measured.",
            source="pwd_parcel",
        )
    if not built:
        return _line(
            "party_wall",
            "clear",
            f"{len(rows)} adjoining parcel(s), none of them built, so no party wall is "
            "implied by the boundaries.",
            source="pwd_parcel",
        )
    named = ", ".join(
        f"{row['address'] or row['parcel_number']} ({row['shared_ft']} ft)" for row in built[:3]
    )
    return _line(
        "party_wall",
        "flag",
        f"{len(built)} built parcel(s) share a boundary: {named}. Where a wall sits on the "
        "line it is a party wall, which a survey confirms and this report cannot.",
        source="pwd_parcel",
    )


def _utilities_line() -> DiligenceLine:
    return _line(
        "utilities_curb",
        "unverified",
        "Not in our data — no dataset LotScope holds publishes water, sewer or gas service "
        "at a parcel, or whether a curb cut exists. Ask PWD and PGW, and look at the kerb.",
        source="none",
    )


def _sheriff_line(result: ToolResult | None) -> DiligenceLine:
    if result is None:
        return _line(
            "sheriff",
            "unverified",
            "The sheriff's listing could not be read for this report.",
            source="sheriff_sale",
        )
    source, url, fetched_at, ingested_at = _stamp(result.sources)
    listings = result.data.get("listings") or []
    if not listings:
        return _line(
            "sheriff",
            "clear",
            "No sheriff-sale listing is on file for this parcel.",
            source=source,
            source_url=url,
            fetched_at=fetched_at,
            ingested_at=ingested_at,
        )
    scheduled = [entry for entry in listings if entry.get("is_scheduled")]
    changes = result.data.get("changes") or []
    if scheduled:
        entry = scheduled[0]
        return _line(
            "sheriff",
            "flag",
            f"Listed for sheriff sale on {entry.get('sale_date')} as case "
            f"{entry.get('case_number')} ({entry.get('status')}), {len(changes)} change(s) "
            "recorded in the last 180 days. The published opening bid is a nominal minimum.",
            source=source,
            source_url=url,
            fetched_at=fetched_at,
            ingested_at=ingested_at,
        )
    entry = listings[0]
    return _line(
        "sheriff",
        "flag",
        f"{len(listings)} past sheriff-sale listing(s); the most recent is case "
        f"{entry.get('case_number')} on {entry.get('sale_date')} ({entry.get('status')}). "
        "A sheriff's deed in the chain changes what a title search must cover.",
        source=source,
        source_url=url,
        fetched_at=fetched_at,
        ingested_at=ingested_at,
    )


async def build_diligence(
    session: AsyncSession,
    parcel_number: str,
    *,
    user_id: int,
    redis: Redis | None = None,
) -> DiligenceReport | None:
    """The checklist for one parcel, live where a buyer would check for themselves."""
    parcel = (await session.execute(_PARCEL_SQL, {"parcel_number": parcel_number})).one_or_none()
    if parcel is None:
        return None

    context = ToolContext(user_id=user_id, redis=redis)
    rtt = await _run_tool(session, context, "live_rtt", parcel.parcel_number)
    li = await _run_tool(session, context, "live_li", parcel.parcel_number)
    sheriff = await _run_tool(session, context, "get_sheriff_listing", parcel.parcel_number)
    delinquency = await _run_tool(session, context, "get_delinquency", parcel.parcel_number)
    overlays = await _run_tool(session, context, "get_overlays_and_flags", parcel.parcel_number)
    neighbours = await _run_tool(session, context, "get_neighbors", parcel.parcel_number)

    historic_line, overlays_line, flood_line = _overlays_line(overlays)
    by_key = {
        "title_chain": _title_chain_line(rtt),
        "delinquency": _delinquency_line(delinquency, parcel.owner),
        "li_open_cases": _li_line(li),
        "adjacent_unsafe": await _adjacent_unsafe_line(session, parcel.parcel_number),
        "conservatorship": _conservatorship_line(),
        "historic": historic_line,
        "overlays_rco": overlays_line,
        "flood": flood_line,
        "public_neighbour": _public_neighbour_line(neighbours),
        "estate_probate": await _estate_line(session, parcel.parcel_number, parcel.owner),
        "party_wall": await _party_wall_line(session, parcel.parcel_number),
        "utilities_curb": _utilities_line(),
        "sheriff": _sheriff_line(sheriff),
    }

    return DiligenceReport(
        parcel_number=parcel.parcel_number,
        address=parcel.address,
        lines=[by_key[key] for key in CHECK_KEYS],
        computed_at=datetime.now(UTC),
    )


async def start_run(session: AsyncSession, user_id: int, parcel_number: str) -> DiligenceRun:
    """Open a run row so the buyer can watch it, then let the worker fill it in."""
    exists = (await session.execute(_PARCEL_SQL, {"parcel_number": parcel_number})).one_or_none()
    if exists is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    run = DiligenceRun(user_id=user_id, parcel_number=parcel_number, status="pending")
    session.add(run)
    await session.flush()
    return run


async def complete_run(
    session: AsyncSession, run_id: int, *, redis: Redis | None = None
) -> DiligenceRun:
    """Build the checklist, render it, and file the PDF against the run."""
    run = await session.get(DiligenceRun, run_id)
    if run is None:
        raise NotFoundError(f"Diligence run {run_id} was not found.")
    try:
        report = await build_diligence(session, run.parcel_number, user_id=run.user_id, redis=redis)
        if report is None:
            raise NotFoundError(f"Parcel {run.parcel_number} was not found.")
        pdf = render_diligence_pdf(report)
    except Exception as cause:
        run.status = "failed"
        run.error = str(cause)
        await session.flush()
        raise

    directory = Path(get_settings().packet_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / diligence_filename(f"{run.parcel_number}-u{run.user_id}")
    path.write_bytes(pdf)

    run.status = "ready"
    run.error = None
    run.pdf_path = str(path)
    run.report_json = report.model_dump(mode="json")
    run.generated_at = datetime.now(UTC)
    await session.flush()
    return run


async def get_run(session: AsyncSession, run_id: int, user_id: int) -> DiligenceRun:
    run = await session.get(DiligenceRun, run_id)
    if run is None or run.user_id != user_id:
        raise NotFoundError(f"Diligence run {run_id} was not found.")
    return run


async def latest_run(
    session: AsyncSession, user_id: int, parcel_number: str
) -> DiligenceRun | None:
    return (
        await session.execute(
            select(DiligenceRun)
            .where(
                DiligenceRun.user_id == user_id,
                DiligenceRun.parcel_number == parcel_number,
                DiligenceRun.status == "ready",
            )
            .order_by(DiligenceRun.generated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
