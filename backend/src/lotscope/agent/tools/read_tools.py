import dataclasses
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.agent.envelope import Source, ToolResult, empty
from lotscope.agent.tools import urls
from lotscope.agent.tools.registry import ToolContext, tool
from lotscope.core.market import MARKET_CODE

WATER_GAS_GAP = "Water and sewer liens and PGW balances are not in any dataset LotScope holds."

_RESOLVE_SQL = text(
    "SELECT parcel_number, address, owner, owner_key FROM parcel "
    "WHERE market_code = :market_code AND ("
    "  lower(parcel_number) = lower(:needle) OR lower(address) = lower(:needle) "
    "  OR address ILIKE :prefix"
    ") ORDER BY (lower(address) = lower(:needle)) DESC, parcel_number LIMIT 1"
)

_FRESHNESS_SQL = text(
    "SELECT dataset, last_success_at FROM dataset_freshness WHERE market_code = :market_code"
)


class ParcelInput(BaseModel):
    parcel: str = Field(
        description="A parcel number such as phl:191357500, or a Philadelphia street address."
    )


async def _resolve(session: AsyncSession, needle: str) -> Any:
    return (
        await session.execute(
            _RESOLVE_SQL,
            {"market_code": MARKET_CODE, "needle": needle.strip(), "prefix": f"{needle.strip()}%"},
        )
    ).one_or_none()


async def _fetched(session: AsyncSession) -> dict[str, datetime]:
    rows = await session.execute(_FRESHNESS_SQL, {"market_code": MARKET_CODE})
    return {row.dataset: row.last_success_at for row in rows if row.last_success_at}


def _source(name: str, url: str, fetched: dict[str, datetime], dataset: str) -> Source:
    return Source(name=name, url=url, fetched_at=fetched.get(dataset))


def _computed(name: str) -> Source:
    return Source(name=name, computed_at=datetime.now(UTC))


@tool(
    name="get_verdict",
    description=(
        "The full computed read on one parcel: buildability, risk score and flags, distress "
        "signals, and the deal — ARV, costs, margin and maximum allowable offer. Everything is "
        "computed when you ask, from current zoning, comps and assessment data, not read from "
        "a stored table. Use this when the buyer asks whether a lot is worth buying or what "
        "they should pay."
    ),
    input_model=ParcelInput,
)
async def get_verdict_tool(
    session: AsyncSession, context: ToolContext, payload: ParcelInput
) -> ToolResult:
    from lotscope.distress.service import assess_parcel_distress
    from lotscope.verdict.service import compute_verdict

    row = await _resolve(session, payload.parcel)
    if row is None:
        return empty(f"No Philadelphia parcel matches {payload.parcel!r}.")

    verdict = await compute_verdict(session, row.parcel_number)
    distress = await assess_parcel_distress(session, row.parcel_number)
    fetched = await _fetched(session)

    unverified = [WATER_GAS_GAP]
    if verdict is None:
        unverified.append(
            f"No verdict could be computed for {row.parcel_number}, so there is no offer figure."
        )

    return ToolResult(
        data={
            "parcel_number": row.parcel_number,
            "address": row.address,
            "verdict": verdict.model_dump(mode="json") if verdict else None,
            "distress": distress.model_dump(mode="json") if distress else None,
        },
        sources=[
            _computed("lotscope_verdict"),
            _source("opa_properties_public", urls.OPA_URL, fetched, "opa_properties_public"),
            _source("rtt_summary", urls.RTT_URL, fetched, "rtt_summary"),
            Source(name="atlas", url=urls.atlas(row.parcel_number)),
        ],
        unverified=unverified,
    )


class ZoningInput(BaseModel):
    parcel: str = Field(description="Parcel number or Philadelphia street address.")
    proposed_use: str | None = Field(
        default=None,
        description="The use the buyer has in mind, such as 'single_family' or 'multi_family'.",
    )
    units: int | None = Field(
        default=None, ge=1, le=200, description="How many units they want to build."
    )


@tool(
    name="get_zoning",
    description=(
        "The zoning read on a parcel: base district, how it was resolved, the standards that "
        "apply after overlays are taken into account, whether anything is buildable by right, "
        "how many units, and the dimensional reasons behind the answer with the Title 14 "
        "provision each came from. Use this whenever the question is about what can legally "
        "be built."
    ),
    input_model=ZoningInput,
)
async def get_zoning_tool(
    session: AsyncSession, context: ToolContext, payload: ZoningInput
) -> ToolResult:
    from lotscope.zoning.service import (
        assess_parcel,
        compute_envelope,
        get_parcel_overlays,
        get_parcel_standard,
    )

    row = await _resolve(session, payload.parcel)
    if row is None:
        return empty(f"No Philadelphia parcel matches {payload.parcel!r}.")

    buildability = await assess_parcel(session, row.parcel_number)
    standard = await get_parcel_standard(session, row.parcel_number)
    overlays = await get_parcel_overlays(session, row.parcel_number)
    envelope = await compute_envelope(session, row.parcel_number)
    fetched = await _fetched(session)

    unverified: list[str] = []
    if buildability is None:
        unverified.append(f"No zoning standard resolved for {row.parcel_number}.")
    elif buildability.confidence == "low":
        unverified.append(
            "The by-right read is low confidence: the district or dimensions are incomplete."
        )
    allowed_units = buildability.by_right_units if buildability else None
    if payload.units is not None and allowed_units is not None and payload.units > allowed_units:
        unverified.append(
            f"{payload.units} units exceeds the {allowed_units} this district allows by right; "
            "the gap would need a variance."
        )

    cited = buildability.cited_section if buildability else None
    return ToolResult(
        data={
            "parcel_number": row.parcel_number,
            "proposed_use": payload.proposed_use,
            "requested_units": payload.units,
            "buildability": buildability.model_dump(mode="json") if buildability else None,
            "effective_standard": dataclasses.asdict(standard) if standard else None,
            "overlays": overlays,
            "envelope": envelope.model_dump(mode="json") if envelope else None,
        },
        sources=[
            _computed("lotscope_buildability"),
            _source("zoning_base_districts", urls.ZONING_URL, fetched, "zoning_base_districts"),
            _source("zoning_overlays", urls.OVERLAY_URL, fetched, "zoning_overlays"),
            Source(name="title_14", url=urls.provision(cited)),
        ],
        unverified=unverified,
    )


class CodeInput(BaseModel):
    provision_id: str | None = Field(
        default=None, description="A Title 14 citation such as '14-701' if you already have one."
    )
    question: str | None = Field(
        default=None,
        description="A plain question about the Philadelphia code when you have no citation.",
    )


@tool(
    name="get_code",
    description=(
        "Read the Philadelphia code itself. Give a provision id to fetch that section, or a "
        "question to search the corpus. Returns the provision text with its citation. Use this "
        "when the buyer asks what the code says, or when you want to quote the rule behind a "
        "zoning answer rather than paraphrase it."
    ),
    input_model=CodeInput,
)
async def get_code_tool(
    session: AsyncSession, context: ToolContext, payload: CodeInput
) -> ToolResult:
    from lotscope.ai.embeddings import VoyageEmbedder
    from lotscope.ai.service import retrieve_code_context
    from lotscope.core.config import get_settings

    query = (payload.provision_id or payload.question or "").strip()
    if not query:
        return empty("No provision id or question was given, so nothing was searched.")

    settings = get_settings()
    if not settings.voyage_api_key:
        return empty("The code corpus is not searchable: no embedding key is configured.")

    documents = await retrieve_code_context(
        session, VoyageEmbedder(settings), query, document_limit=5
    )
    if not documents:
        return empty(f"Nothing in the Philadelphia code corpus matched {query!r}.")

    return ToolResult(
        data={
            "query": query,
            "provisions": [
                {
                    "cite": document.section,
                    "title": document.title,
                    "text": document.content,
                    "source": document.source,
                }
                for document in documents
            ],
        },
        sources=[
            Source(name="phillycode", url=urls.provision(documents[0].section)),
        ],
        unverified=[
            "Code text is the corpus as ingested; check the live code for amendments since."
        ],
    )


class CompsInput(BaseModel):
    parcel: str = Field(description="Parcel number or Philadelphia street address.")
    radius_m: float | None = Field(
        default=None, ge=50, le=3000, description="Search radius in metres."
    )
    months: int | None = Field(
        default=None, ge=3, le=120, description="How far back to look, in months."
    )


@tool(
    name="get_comps",
    description=(
        "Comparable recorded sales near a parcel, with the price range and why each comp was "
        "included. Use this when the buyer asks what a lot is worth or challenges a valuation. "
        "These are recorded deeds, not listings or estimates."
    ),
    input_model=CompsInput,
)
async def get_comps_tool(
    session: AsyncSession, context: ToolContext, payload: CompsInput
) -> ToolResult:
    from lotscope.valuation.service import value_parcel

    row = await _resolve(session, payload.parcel)
    if row is None:
        return empty(f"No Philadelphia parcel matches {payload.parcel!r}.")

    radius = payload.radius_m or 1500.0
    years = max(1, round((payload.months or 36) / 12))
    valuation = await value_parcel(
        session, row.parcel_number, radius_ft=radius / 0.3048, years=years
    )
    fetched = await _fetched(session)

    if valuation is None:
        return ToolResult(
            data={"parcel_number": row.parcel_number, "comps": []},
            sources=[_source("rtt_summary", urls.RTT_URL, fetched, "rtt_summary")],
            unverified=["No valuation could be produced, so there are no comps to show."],
        )

    prices = [comp.sale_price for comp in valuation.comps]
    unverified: list[str] = []
    if not valuation.comps:
        unverified.append(
            f"No recorded sale within {radius:.0f} m in {years * 12} months matched this lot."
        )
    if valuation.confidence == "low":
        unverified.append(
            "Confidence is low: the comp set is thin, so treat the estimate as indicative."
        )

    return ToolResult(
        data={
            "parcel_number": row.parcel_number,
            "estimate": valuation.estimate,
            "low": valuation.low,
            "high": valuation.high,
            "confidence": valuation.confidence,
            "radius_m": radius,
            "months": years * 12,
            "comp_range": {"low": min(prices), "high": max(prices)} if prices else None,
            "comps": [comp.model_dump(mode="json") for comp in valuation.comps],
            "reasons": valuation.reasons,
        },
        sources=[
            _computed("lotscope_valuation"),
            _source("rtt_summary", urls.RTT_URL, fetched, "rtt_summary"),
        ],
        unverified=unverified,
    )


@tool(
    name="get_sheriff_clearing",
    description=(
        "What sheriff sales actually clear for near this parcel: the median consideration of "
        "sheriff's deeds on comparable vacant land nearby, with the sample size and range. Use "
        "this to answer what a lot will really cost at auction. The published opening bid is a "
        "nominal minimum on tax sales and is not a price."
    ),
    input_model=ParcelInput,
)
async def get_sheriff_clearing_tool(
    session: AsyncSession, context: ToolContext, payload: ParcelInput
) -> ToolResult:
    from lotscope.valuation.service import sheriff_clearing_estimate

    row = await _resolve(session, payload.parcel)
    if row is None:
        return empty(f"No Philadelphia parcel matches {payload.parcel!r}.")

    estimate = await sheriff_clearing_estimate(session, row.parcel_number)
    fetched = await _fetched(session)

    return ToolResult(
        data={"parcel_number": row.parcel_number, **estimate.model_dump(mode="json")},
        sources=[
            _computed("lotscope_clearing_estimate"),
            _source("rtt_summary", urls.RTT_URL, fetched, "rtt_summary"),
        ],
        unverified=[] if estimate.sufficient else [estimate.reason or "Not enough nearby deeds."],
    )


@tool(
    name="get_deed_chain",
    description=(
        "Every recorded transfer of this parcel: grantor, grantee, consideration, document id "
        "and date, newest first. Use this to answer who owns it, what they paid, when they "
        "bought, and whether a sheriff's deed sits in the chain. Recorded deeds only — nothing "
        "here says why anyone sold."
    ),
    input_model=ParcelInput,
)
async def get_deed_chain_tool(
    session: AsyncSession, context: ToolContext, payload: ParcelInput
) -> ToolResult:
    row = await _resolve(session, payload.parcel)
    if row is None:
        return empty(f"No Philadelphia parcel matches {payload.parcel!r}.")

    deeds = (
        (
            await session.execute(
                text(
                    "SELECT sale_date, sale_price, document_type, document_id, grantor, grantee "
                    "FROM sale WHERE parcel_number = :p ORDER BY sale_date DESC NULLS LAST LIMIT 25"
                ),
                {"p": row.parcel_number},
            )
        )
        .mappings()
        .all()
    )
    fetched = await _fetched(session)

    unverified: list[str] = []
    if not deeds:
        unverified.append(f"No recorded transfer is on file for {row.parcel_number}.")
    if any(deed["grantee"] is None for deed in deeds):
        unverified.append("Some transfers carry no party names in the recorded data.")

    return ToolResult(
        data={
            "parcel_number": row.parcel_number,
            "current_owner": row.owner,
            "deeds": [
                {
                    "sale_date": deed["sale_date"].isoformat() if deed["sale_date"] else None,
                    "consideration": float(deed["sale_price"]) if deed["sale_price"] else None,
                    "document_type": deed["document_type"],
                    "document_id": deed["document_id"],
                    "grantor": deed["grantor"],
                    "grantee": deed["grantee"],
                }
                for deed in deeds
            ],
        },
        sources=[
            _source("rtt_summary", urls.RTT_URL, fetched, "rtt_summary"),
            Source(name="atlas", url=urls.atlas(row.parcel_number)),
        ],
        unverified=unverified,
    )


@tool(
    name="get_violations",
    description=(
        "Licences and Inspections violations on this parcel: how many are open versus on "
        "record, the case status of each, and whether any names an unsafe or imminently "
        "dangerous structure. Use this when the buyer asks what is wrong with a lot or what "
        "they would inherit."
    ),
    input_model=ParcelInput,
)
async def get_violations_tool(
    session: AsyncSession, context: ToolContext, payload: ParcelInput
) -> ToolResult:
    from lotscope.risk.service import get_violation_posture

    row = await _resolve(session, payload.parcel)
    if row is None:
        return empty(f"No Philadelphia parcel matches {payload.parcel!r}.")

    posture = await get_violation_posture(session, row.parcel_number)
    events = (
        (
            await session.execute(
                text(
                    "SELECT event_type, status, case_status, event_date, description, "
                    "is_unsafe, is_imminently_dangerous FROM li_event "
                    "WHERE parcel_number = :p AND event_type = 'violation' "
                    "ORDER BY event_date DESC NULLS LAST LIMIT 25"
                ),
                {"p": row.parcel_number},
            )
        )
        .mappings()
        .all()
    )
    fetched = await _fetched(session)

    return ToolResult(
        data={
            "parcel_number": row.parcel_number,
            "posture": posture.model_dump(mode="json"),
            "violations": [
                {
                    "event_date": e["event_date"].isoformat() if e["event_date"] else None,
                    "status": e["status"],
                    "case_status": e["case_status"],
                    "description": e["description"],
                    "unsafe": bool(e["is_unsafe"]),
                    "imminently_dangerous": bool(e["is_imminently_dangerous"]),
                }
                for e in events
            ],
        },
        sources=[
            _source("li_event", urls.LI_URL, fetched, "violations"),
            Source(name="li_property_history", url=urls.li_history(row.address)),
        ],
        unverified=[
            "L&I records what was reported and inspected; an unreported condition is invisible "
            "here."
        ],
    )


@tool(
    name="get_delinquency",
    description=(
        "The tax posture of a parcel: whether it is delinquent, how much is owed, and who the "
        "debt is recorded against. The named debtor matters — a debt against a prior owner may "
        "have been discharged at a sheriff sale. Say who it names and when it was measured; do "
        "not assume the current owner owes it."
    ),
    input_model=ParcelInput,
)
async def get_delinquency_tool(
    session: AsyncSession, context: ToolContext, payload: ParcelInput
) -> ToolResult:
    row = await _resolve(session, payload.parcel)
    if row is None:
        return empty(f"No Philadelphia parcel matches {payload.parcel!r}.")

    tax = (
        (
            await session.execute(
                text(
                    "SELECT is_delinquent, total_due, principal_due, years_owed, lien_count, "
                    "as_of_date, delinquency_owner, snapshot_period FROM tax_status "
                    "WHERE parcel_number = :p"
                ),
                {"p": row.parcel_number},
            )
        )
        .mappings()
        .one_or_none()
    )

    latest_deed = (
        (
            await session.execute(
                text(
                    "SELECT sale_date, document_type, grantee FROM sale WHERE parcel_number = :p "
                    "ORDER BY sale_date DESC NULLS LAST LIMIT 1"
                ),
                {"p": row.parcel_number},
            )
        )
        .mappings()
        .one_or_none()
    )
    fetched = await _fetched(session)

    unverified = [WATER_GAS_GAP]
    attribution = None
    if tax is None:
        unverified.append(f"No tax record is on file for {row.parcel_number}.")
    else:
        debtor = tax["delinquency_owner"]
        if debtor and row.owner and debtor.strip().upper() != row.owner.strip().upper():
            attribution = (
                f"The debt is recorded against {debtor}, not the current owner {row.owner}."
            )
            if (
                latest_deed
                and latest_deed["sale_date"]
                and tax["as_of_date"]
                and latest_deed["sale_date"] > tax["as_of_date"]
            ):
                attribution += (
                    f" A {latest_deed['document_type']} dated "
                    f"{latest_deed['sale_date'].isoformat()} post-dates the "
                    f"{tax['as_of_date'].isoformat()} tax snapshot, so it may have been "
                    "discharged at that transfer."
                )
            unverified.append(
                "Whether the recorded debt survived the last transfer is not in our data; the "
                "Department of Revenue is the only place to confirm it."
            )

    return ToolResult(
        data={
            "parcel_number": row.parcel_number,
            "current_owner": row.owner,
            "tax": {
                key: (value.isoformat() if hasattr(value, "isoformat") else value)
                for key, value in (dict(tax).items() if tax else [])
            },
            "attribution": attribution,
            "latest_transfer": {
                "sale_date": latest_deed["sale_date"].isoformat()
                if latest_deed and latest_deed["sale_date"]
                else None,
                "document_type": latest_deed["document_type"] if latest_deed else None,
            },
        },
        sources=[
            _source("tax_status", urls.TAX_URL, fetched, "real_estate_tax_delinquencies"),
            _source("rtt_summary", urls.RTT_URL, fetched, "rtt_summary"),
        ],
        unverified=unverified,
    )


class SheriffListingInput(BaseModel):
    parcel: str | None = Field(
        default=None, description="Parcel number or address, for one lot's listing."
    )
    sale_date: str | None = Field(
        default=None, description="An ISO date such as 2026-09-16, for a whole sale list."
    )


@tool(
    name="get_sheriff_listing",
    description=(
        "Sheriff-sale listings and the changes recorded against them. Give a parcel for one "
        "lot, or a sale date for the whole list. A listing whose status reads Postponed but "
        "whose date is still in the future is scheduled — the status names the date that "
        "moved, not the case. Opening bid is a published minimum, nominal on tax sales."
    ),
    input_model=SheriffListingInput,
)
async def get_sheriff_listing_tool(
    session: AsyncSession, context: ToolContext, payload: SheriffListingInput
) -> ToolResult:
    from lotscope.risk.service import NOT_SCHEDULED_STATUSES, recent_sheriff_changes

    fetched = await _fetched(session)
    sources = [
        _source("sheriff_sale", urls.CIVILVIEW, fetched, "sheriff_sale"),
        Source(name="civilview", url=urls.CIVILVIEW),
    ]

    if payload.parcel:
        row = await _resolve(session, payload.parcel)
        if row is None:
            return empty(f"No Philadelphia parcel matches {payload.parcel!r}.")
        listings = (
            (
                await session.execute(
                    text(
                        "SELECT case_number, sale_type, sale_date, status, opening_bid, plaintiff "
                        "FROM sheriff_sale WHERE parcel_number = :p "
                        "ORDER BY sale_date DESC NULLS LAST LIMIT 10"
                    ),
                    {"p": row.parcel_number},
                )
            )
            .mappings()
            .all()
        )
        changes = await recent_sheriff_changes(session, row.parcel_number, days=180)
        today = datetime.now(UTC).date()
        return ToolResult(
            data={
                "parcel_number": row.parcel_number,
                "listings": [
                    {
                        "case_number": entry["case_number"],
                        "sale_type": entry["sale_type"],
                        "sale_date": entry["sale_date"].isoformat() if entry["sale_date"] else None,
                        "status": entry["status"],
                        "opening_bid": float(entry["opening_bid"])
                        if entry["opening_bid"]
                        else None,
                        "plaintiff": entry["plaintiff"],
                        "is_scheduled": bool(
                            entry["sale_date"]
                            and entry["sale_date"] >= today
                            and (entry["status"] or "") not in NOT_SCHEDULED_STATUSES
                        ),
                    }
                    for entry in listings
                ],
                "changes": [change.model_dump(mode="json") for change in changes],
            },
            sources=sources,
            unverified=[
                "The published opening bid is a minimum and is nominal on tax sales.",
                "Anything announced on the sale day itself is not in this data.",
            ]
            + ([] if listings else [f"{row.parcel_number} has no sheriff-sale listing on file."]),
        )

    if not payload.sale_date:
        return empty("Give either a parcel or a sale date.")

    rows = (
        (
            await session.execute(
                text(
                    "SELECT ss.parcel_number, p.address, ss.case_number, ss.status, "
                    "ss.opening_bid, p.is_vacant FROM sheriff_sale ss "
                    "JOIN parcel p USING (parcel_number) WHERE ss.sale_date = :d "
                    "ORDER BY ss.parcel_number LIMIT 400"
                ),
                {"d": payload.sale_date},
            )
        )
        .mappings()
        .all()
    )

    return ToolResult(
        data={
            "sale_date": payload.sale_date,
            "listings": len(rows),
            "vacant": sum(1 for entry in rows if entry["is_vacant"]),
            "results": [dict(entry) for entry in rows[:100]],
        },
        sources=sources,
        unverified=[] if rows else [f"No listing is recorded for {payload.sale_date}."],
    )


@tool(
    name="get_neighbors",
    description=(
        "The parcels sharing a boundary with this one: who owns each, whether it is vacant, "
        "whether it is publicly held, and how much boundary they share. Use this for "
        "assemblage questions — whether buying next door unlocks a buildable footprint."
    ),
    input_model=ParcelInput,
)
async def get_neighbors_tool(
    session: AsyncSession, context: ToolContext, payload: ParcelInput
) -> ToolResult:
    from lotscope.assemblage.service import compute_assemblage

    row = await _resolve(session, payload.parcel)
    if row is None:
        return empty(f"No Philadelphia parcel matches {payload.parcel!r}.")

    assemblage = await compute_assemblage(session, row.parcel_number)
    fetched = await _fetched(session)

    owned = {parcel.lower() for parcel in context.owned_parcels}
    neighbours = []
    for neighbour in assemblage.neighbors if assemblage else []:
        entry = neighbour.model_dump(mode="json")
        entry["already_owned_by_this_buyer"] = neighbour.parcel_number.lower() in owned
        neighbours.append(entry)

    return ToolResult(
        data={
            "parcel_number": row.parcel_number,
            "neighbors": neighbours,
            "summary": assemblage.summary.model_dump(mode="json")
            if assemblage and assemblage.summary
            else None,
            "reasons": assemblage.reasons if assemblage else [],
        },
        sources=[
            _computed("lotscope_assemblage"),
            _source("pwd_parcel", urls.PWD_URL, fetched, "pwd_parcels"),
            _source("opa_properties_public", urls.OPA_URL, fetched, "opa_properties_public"),
        ],
        unverified=[]
        if assemblage
        else [f"No adjacency could be computed for {row.parcel_number}."],
    )


@tool(
    name="get_overlays_and_flags",
    description=(
        "Everything layered over a parcel: zoning overlays, historic district, flood hazard "
        "area, and the Registered Community Organizations that must be notified before a "
        "variance hearing. Use this when the buyer asks what extra review a lot carries."
    ),
    input_model=ParcelInput,
)
async def get_overlays_and_flags_tool(
    session: AsyncSession, context: ToolContext, payload: ParcelInput
) -> ToolResult:
    from lotscope.zoning.service import get_parcel_overlays

    row = await _resolve(session, payload.parcel)
    if row is None:
        return empty(f"No Philadelphia parcel matches {payload.parcel!r}.")

    overlays = await get_parcel_overlays(session, row.parcel_number)
    flags = (
        (
            await session.execute(
                text(
                    "SELECT "
                    "EXISTS (SELECT 1 FROM historic_district h JOIN parcel p2 "
                    "  ON ST_Intersects(h.geom_local, p2.geom_local) "
                    "  WHERE p2.parcel_number = :p) AS historic, "
                    "EXISTS (SELECT 1 FROM flood_zone f JOIN parcel p3 "
                    "  ON ST_Intersects(f.geom_local, p3.geom_local) "
                    "  WHERE p3.parcel_number = :p AND (upper(f.zone) LIKE 'A%' "
                    "  OR upper(f.zone) LIKE 'V%')) AS sfha"
                ),
                {"p": row.parcel_number},
            )
        )
        .mappings()
        .one()
    )

    rcos = (
        (
            await session.execute(
                text(
                    "SELECT r.name FROM rco r JOIN parcel p ON "
                    "ST_Intersects(r.geom_local, p.geom_local) "
                    "WHERE p.parcel_number = :p ORDER BY r.name LIMIT 10"
                ),
                {"p": row.parcel_number},
            )
        )
        .scalars()
        .all()
    )
    fetched = await _fetched(session)

    return ToolResult(
        data={
            "parcel_number": row.parcel_number,
            "overlays": overlays,
            "in_historic_district": bool(flags["historic"]),
            "in_flood_hazard_area": bool(flags["sfha"]),
            "rcos": list(rcos),
        },
        sources=[
            _source("zoning_overlays", urls.OVERLAY_URL, fetched, "zoning_overlays"),
            _source(
                "historicdistricts_local", urls.HISTORIC_URL, fetched, "historicdistricts_local"
            ),
            Source(name="fema_flood", url=urls.FLOOD_URL),
            _source("zoning_rco", urls.RCO_URL, fetched, "zoning_rco"),
        ],
        unverified=[
            "Overlay and district boundaries are as mapped; a boundary-line lot is worth "
            "checking against the official map."
        ],
    )


class OwnerInput(BaseModel):
    parcel: str | None = Field(
        default=None, description="A parcel whose owner you want the portfolio for."
    )
    owner_key: str | None = Field(
        default=None, description="A normalised owner name if you already have one."
    )


@tool(
    name="get_owner_portfolio",
    description=(
        "Other Philadelphia parcels held under the same normalised owner name, with how many "
        "are vacant and what they are worth. Use this to see whether an owner is a one-lot "
        "holder or a portfolio. Name matching is by normalised string, so distinct people "
        "sharing a name will merge — say so."
    ),
    input_model=OwnerInput,
)
async def get_owner_portfolio_tool(
    session: AsyncSession, context: ToolContext, payload: OwnerInput
) -> ToolResult:
    owner_key = payload.owner_key
    subject = None
    if owner_key is None:
        if not payload.parcel:
            return empty("Give either a parcel or an owner key.")
        subject = await _resolve(session, payload.parcel)
        if subject is None:
            return empty(f"No Philadelphia parcel matches {payload.parcel!r}.")
        owner_key = subject.owner_key
    if not owner_key:
        return empty("That parcel has no owner name on record, so no portfolio can be built.")

    rows = (
        (
            await session.execute(
                text(
                    "SELECT parcel_number, address, is_vacant, market_value, mailing_address "
                    "FROM parcel WHERE market_code = :m AND owner_key = :k "
                    "ORDER BY parcel_number LIMIT 200"
                ),
                {"m": MARKET_CODE, "k": owner_key},
            )
        )
        .mappings()
        .all()
    )
    fetched = await _fetched(session)

    return ToolResult(
        data={
            "owner_key": owner_key,
            "subject_parcel": subject.parcel_number if subject else None,
            "count": len(rows),
            "vacant": sum(1 for entry in rows if entry["is_vacant"]),
            "parcels": [
                {
                    "parcel_number": entry["parcel_number"],
                    "address": entry["address"],
                    "is_vacant": bool(entry["is_vacant"]),
                    "market_value": float(entry["market_value"]) if entry["market_value"] else None,
                }
                for entry in rows[:50]
            ],
        },
        sources=[_source("opa_properties_public", urls.OPA_URL, fetched, "opa_properties_public")],
        unverified=[
            "Owner matching is by normalised name only: two different people with the same "
            "name merge into one portfolio here, and one person using two spellings splits.",
        ],
    )
