"""Re-read the two facts that move, for the lots a buyer might actually bid on.

A packet is read at an auction, hours or days after the nightly ingest wrote the numbers in
it. Open violations and sale status are what change in that gap and what cost money, so for
every BID and LOOK lot they are read from the primary source at build time and printed beside
the stored value with both timestamps.

PASS lots stay on the index. Re-reading a hundred lots the buyer has already been told to
skip spends their time and the city's servers to change nothing.

This reuses the Analyst's live tools rather than a second implementation: same requests, same
cache, same correction filing, so a packet and a conversation can never disagree about what
the source says.
"""

from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.agent.tools.live_tools import (
    SheriffInput,
    live_li_tool,
    live_sheriff_tool,
)
from lotscope.agent.tools.read_tools import ParcelInput
from lotscope.agent.tools.registry import ToolContext
from lotscope.core.logging import get_logger
from lotscope.packet.schemas import LiveCheck, PacketLot

VERIFIED_VERDICTS = ("BID", "LOOK")

_logger = get_logger(__name__)


def _source(envelope: Any, live: bool) -> tuple[str, str | None, Any]:
    for entry in envelope.sources:
        if entry.name.endswith("(live)") is live:
            return entry.name, entry.url, (entry.fetched_at if live else entry.ingested_at)
    return ("unknown", None, None)


def _violation_check(envelope: Any) -> LiveCheck:
    data = envelope.data
    stored = data.get("stored") or {}
    live = data.get("live")
    live_name, live_url, fetched_at = _source(envelope, live=True)
    _, stored_url, ingested_at = _source(envelope, live=False)

    if live is None:
        return LiveCheck(
            field="open_violations",
            stored=str(stored.get("open_violations", "unknown")),
            live=None,
            agrees=False,
            note="The live L&I read did not come back. Treat the stored count as unverified.",
            source=live_name,
            source_url=live_url or stored_url,
            ingested_at=ingested_at,
            fetched_at=fetched_at,
        )

    stored_open = stored.get("open_violations")
    live_open = live.get("open_violations")
    agrees = stored_open == live_open
    if agrees:
        note = "L&I agrees with our count."
    elif data.get("opened_since_our_last_read") or data.get("changed_since_our_last_read"):
        note = (
            f"L&I shows {live_open} open, we hold {stored_open}. Cases have opened or changed "
            f"since our last read; the live number is the one to work from."
        )
    else:
        note = (
            f"L&I shows {live_open} open, we hold {stored_open}. The difference is violations "
            f"our history never held, not activity since the last read — check L&I directly "
            f"before you price the clean-up."
        )
    return LiveCheck(
        field="open_violations",
        stored=str(stored_open),
        live=str(live_open),
        agrees=agrees,
        note=note,
        source=live_name,
        source_url=live_url,
        ingested_at=ingested_at,
        fetched_at=fetched_at,
        correction_id=data.get("correction_filed"),
    )


def _sale_check(envelope: Any) -> LiveCheck:
    data = envelope.data
    stored = data.get("stored") or {}
    live = data.get("live")
    live_name, live_url, fetched_at = _source(envelope, live=True)
    _, stored_url, ingested_at = _source(envelope, live=False)

    stored_text = f"{stored.get('status') or 'unknown'} on {stored.get('sale_date') or 'no date'}"
    if live is None:
        listed_note = next(
            (note for note in envelope.unverified if "sale list" in note),
            "The live sheriff read did not come back.",
        )
        return LiveCheck(
            field="sale_status",
            stored=stored_text,
            live=None,
            agrees=False,
            note=f"{listed_note} Treat the stored status as unverified.",
            source=live_name,
            source_url=live_url or stored_url,
            ingested_at=ingested_at,
            fetched_at=fetched_at,
        )

    live_text = f"{live.get('status') or 'unknown'} on {live.get('sale_date') or 'no date'}"
    agrees = not data.get("diff")
    if agrees:
        note = "The sheriff's site agrees with our listing."
    else:
        note = (
            f"The sheriff's site now shows {live_text}; we hold {stored_text}. "
            f"The live status is the one that decides whether you turn up."
        )
        if int(data.get("stored_cases_on_file") or 0) > 1:
            note += f" This is case {data.get('compared_case')}; the parcel carries more than one."
    return LiveCheck(
        field="sale_status",
        stored=stored_text,
        live=live_text,
        agrees=agrees,
        note=note,
        source=live_name,
        source_url=live_url,
        ingested_at=ingested_at,
        fetched_at=fetched_at,
        correction_id=data.get("correction_filed"),
    )


async def verify_lots(
    session: AsyncSession,
    lots: list[PacketLot],
    *,
    user_id: int,
    redis: Redis | None = None,
) -> int:
    """Attach live checks to every BID and LOOK lot. Returns how many disagreed."""
    context = ToolContext(user_id=user_id, redis=redis)
    disagreed = 0

    for lot in lots:
        if lot.verdict not in VERIFIED_VERDICTS:
            continue
        checks: list[LiveCheck] = []
        try:
            checks.append(
                _violation_check(
                    await live_li_tool(session, context, ParcelInput(parcel=lot.parcel_number))
                )
            )
        except Exception as cause:
            _logger.error("packet_live_li_failed", parcel=lot.parcel_number, error=str(cause))
        try:
            reference = lot.case_number or lot.parcel_number
            checks.append(
                _sale_check(
                    await live_sheriff_tool(session, context, SheriffInput(reference=reference))
                )
            )
        except Exception as cause:
            _logger.error("packet_live_sheriff_failed", parcel=lot.parcel_number, error=str(cause))

        lot.live_checks = checks
        if any(not check.agrees for check in checks):
            disagreed += 1
    return disagreed
