from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.agent.alerts import AgentAlert
from lotscope.agent.envelope import Source, ToolResult, empty
from lotscope.agent.tools import urls
from lotscope.agent.tools.read_tools import _fetched, _resolve
from lotscope.agent.tools.registry import ToolContext, tool
from lotscope.core.market import MARKET_CODE

MAX_SCREEN_PARCELS = 200

DealStage = Literal["lead", "diligence", "offer", "under_contract", "closed", "lost"]


def _computed(name: str) -> Source:
    return Source(name=name, computed_at=datetime.now(UTC))


class DealOverrides(BaseModel):
    construction_cost_per_sqft: float | None = Field(
        default=None, gt=0, le=2000, description="Override the build cost for this call only."
    )
    soft_cost_pct: float | None = Field(default=None, ge=0, le=1)
    selling_cost_pct: float | None = Field(default=None, ge=0, le=1)
    target_margin: float | None = Field(default=None, ge=0, lt=1)


class ComputeDealInput(BaseModel):
    parcel: str = Field(description="Parcel number or Philadelphia street address.")
    overrides: DealOverrides | None = Field(
        default=None,
        description=(
            "Assumptions to change for this calculation only. Leave unset to use the buyer's "
            "saved buy box, which is what they normally underwrite with."
        ),
    )


@tool(
    name="compute_deal",
    description=(
        "Underwrite a parcel: ARV, construction and soft costs, margin and the maximum "
        "allowable offer. Uses the buyer's saved assumptions unless you override them for this "
        "call. Use it to answer 'what should I pay' and to test a what-if without changing "
        "their buy box."
    ),
    input_model=ComputeDealInput,
)
async def compute_deal_tool(
    session: AsyncSession, context: ToolContext, payload: ComputeDealInput
) -> ToolResult:
    from lotscope.deal.service import analyze_parcel_deal

    row = await _resolve(session, payload.parcel)
    if row is None:
        return empty(f"No Philadelphia parcel matches {payload.parcel!r}.")

    overrides = payload.overrides or DealOverrides()
    result = await analyze_parcel_deal(
        session,
        row.parcel_number,
        user_id=context.user_id,
        construction_cost_per_sqft=overrides.construction_cost_per_sqft,
        soft_cost_pct=overrides.soft_cost_pct,
        selling_cost_pct=overrides.selling_cost_pct,
        target_margin=overrides.target_margin,
    )
    if result is None:
        return empty(f"No deal could be computed for {row.parcel_number}.")

    fetched = await _fetched(session)
    changed = overrides.model_dump(exclude_none=True)
    return ToolResult(
        data={
            "parcel_number": row.parcel_number,
            "overrides_applied": changed,
            "assumptions_source": result.assumptions_source,
            "deal": result.model_dump(mode="json"),
        },
        sources=[
            _computed("lotscope_deal"),
            Source(name="rtt_summary", url=urls.RTT_URL, ingested_at=fetched.get("rtt_summary")),
        ],
        unverified=(
            ["These figures use overrides you supplied, not the buyer's saved assumptions."]
            if changed
            else []
        ),
    )


@tool(
    name="run_sensitivity",
    description=(
        "How the margin moves when exit price and build cost move. Returns a grid so you can "
        "say which assumption the deal actually turns on. Use it when a deal is marginal."
    ),
    input_model=ComputeDealInput,
)
async def run_sensitivity_tool(
    session: AsyncSession, context: ToolContext, payload: ComputeDealInput
) -> ToolResult:
    from lotscope.deal.service import analyze_parcel_scenarios

    row = await _resolve(session, payload.parcel)
    if row is None:
        return empty(f"No Philadelphia parcel matches {payload.parcel!r}.")

    overrides = payload.overrides or DealOverrides()
    scenarios = await analyze_parcel_scenarios(
        session,
        row.parcel_number,
        user_id=context.user_id,
        construction_cost_per_sqft=overrides.construction_cost_per_sqft,
        soft_cost_pct=overrides.soft_cost_pct,
        selling_cost_pct=overrides.selling_cost_pct,
        target_margin=overrides.target_margin,
    )
    if scenarios is None:
        return empty(f"No scenarios could be computed for {row.parcel_number}.")

    return ToolResult(
        data={
            "parcel_number": row.parcel_number,
            "scenarios": scenarios.model_dump(mode="json"),
        },
        sources=[_computed("lotscope_sensitivity")],
        unverified=[],
    )


class ScreenSaleInput(BaseModel):
    sale_date: str = Field(description="The sheriff-sale date to screen, as YYYY-MM-DD.")


@tool(
    name="screen_sale",
    description=(
        "Build this buyer's Sale Packet for a sheriff-sale date: every vacant lot on the list "
        "screened against their buy box, graded BID, LOOK or PASS. Returns the packet id and "
        "the split. Use it when they ask what is worth bidding on a date."
    ),
    input_model=ScreenSaleInput,
)
async def screen_sale_tool(
    session: AsyncSession, context: ToolContext, payload: ScreenSaleInput
) -> ToolResult:
    from lotscope.packet.service import build_packet

    try:
        sale_date = date.fromisoformat(payload.sale_date)
    except ValueError:
        return empty(f"{payload.sale_date!r} is not a date in YYYY-MM-DD form.")

    listings = await session.scalar(
        text("SELECT count(*) FROM sheriff_sale WHERE sale_date = :d"), {"d": sale_date}
    )
    if not listings:
        return empty(f"No sheriff-sale listing is recorded for {sale_date.isoformat()}.")

    packet = await build_packet(session, context.user_id, sale_date)
    packet.agent_run_id = context.agent_run_id
    await session.flush()

    model = packet.model_json or {}
    header = model.get("header", {})
    lots = model.get("lots", [])
    return ToolResult(
        data={
            "packet_id": packet.id,
            "sale_date": sale_date.isoformat(),
            "listings": header.get("listings"),
            "vacant": header.get("vacant"),
            "graded_as": header.get("target_use"),
            "bid": sum(1 for lot in lots if lot["verdict"] == "BID"),
            "look": sum(1 for lot in lots if lot["verdict"] == "LOOK"),
            "pass": len(model.get("passed", [])),
            "lots": [
                {
                    "parcel_number": lot["parcel_number"],
                    "address": lot["address"],
                    "verdict": lot["verdict"],
                    "grade_rule": lot["grade_rule"],
                    "verdict_reason": lot["verdict_reason"],
                }
                for lot in lots
            ],
        },
        sources=[_computed("lotscope_packet")],
        unverified=[
            "The published opening bid is a minimum and is nominal on tax sales.",
            "Water and gas liens are not in any dataset LotScope holds.",
        ],
    )


class ScreenParcelsInput(BaseModel):
    parcel_numbers: list[str] | None = Field(
        default=None,
        max_length=MAX_SCREEN_PARCELS,
        description=f"Up to {MAX_SCREEN_PARCELS} parcels to screen against the buy box.",
    )
    center_lat: float | None = None
    center_lng: float | None = None
    radius_m: float | None = Field(default=None, ge=10, le=5000)


@tool(
    name="screen_parcels",
    description=(
        "Screen an arbitrary set of lots against this buyer's buy box and return the same "
        "BID / LOOK / PASS grades a Sale Packet uses. Give explicit parcel numbers, or a "
        "centre and radius to screen an area."
    ),
    input_model=ScreenParcelsInput,
)
async def screen_parcels_tool(
    session: AsyncSession, context: ToolContext, payload: ScreenParcelsInput
) -> ToolResult:
    from lotscope.buybox.service import read_buy_box
    from lotscope.packet.compose import LotInputs, decide
    from lotscope.underwriting.matching import required_margin

    parcels = list(payload.parcel_numbers or [])
    if not parcels:
        if payload.center_lat is None or payload.center_lng is None:
            return empty("Give either parcel numbers or a centre point with a radius.")
        parcels = list(
            (
                await session.execute(
                    text(
                        "SELECT parcel_number FROM parcel WHERE market_code = :m "
                        "AND geom_4326 IS NOT NULL AND ST_DWithin("
                        "  geography(geom_4326), "
                        "  geography(ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)), :radius) "
                        "ORDER BY parcel_number LIMIT :limit"
                    ),
                    {
                        "m": MARKET_CODE,
                        "lng": payload.center_lng,
                        "lat": payload.center_lat,
                        "radius": payload.radius_m or 500.0,
                        "limit": MAX_SCREEN_PARCELS,
                    },
                )
            ).scalars()
        )
    if not parcels:
        return empty("No parcel matched that set or area.")

    buy_box = await read_buy_box(session, context.user_id)
    margin = buy_box.assumptions.get("target_margin", required_margin(buy_box))
    today = datetime.now(UTC).date()

    rows = (
        (
            await session.execute(
                text(
                    "SELECT p.parcel_number, p.address, p.is_vacant, p.lot_area_sqft, "
                    "p.base_zoning_code, v.can_build_by_right, v.by_right_units, "
                    "v.max_allowable_offer, v.est_margin "
                    "FROM parcel p LEFT JOIN parcel_verdict v USING (parcel_number) "
                    "WHERE p.parcel_number = ANY(:parcels)"
                ),
                {"parcels": parcels[:MAX_SCREEN_PARCELS]},
            )
        )
        .mappings()
        .all()
    )

    graded = []
    for row in rows:
        lot = LotInputs(
            parcel_number=row["parcel_number"],
            address=row["address"],
            is_vacant=bool(row["is_vacant"]),
            lot_area_sqft=float(row["lot_area_sqft"]) if row["lot_area_sqft"] else None,
            zoning_code=row["base_zoning_code"],
            can_build_by_right=row["can_build_by_right"],
            by_right_units=row["by_right_units"],
            max_allowable_offer=float(row["max_allowable_offer"])
            if row["max_allowable_offer"] is not None
            else None,
            est_margin=float(row["est_margin"]) if row["est_margin"] is not None else None,
            sale_date=today,
        )
        verdict, reason, rule, _also = decide(lot, buy_box, margin)
        graded.append(
            {
                "parcel_number": row["parcel_number"],
                "address": row["address"],
                "verdict": verdict,
                "grade_rule": rule,
                "reason": reason,
            }
        )

    graded.sort(key=lambda item: {"BID": 0, "LOOK": 1, "PASS": 2}[item["verdict"]])
    return ToolResult(
        data={
            "screened": len(graded),
            "requested": len(parcels),
            "bid": sum(1 for g in graded if g["verdict"] == "BID"),
            "look": sum(1 for g in graded if g["verdict"] == "LOOK"),
            "pass": sum(1 for g in graded if g["verdict"] == "PASS"),
            "results": graded,
        },
        sources=[_computed("lotscope_screen")],
        unverified=(
            [
                "Verdicts here are the stored sweep, not recomputed per lot; ask for one lot to "
                "get a fresh number."
            ]
            if graded
            else ["Nothing was screened."]
        ),
    )


class AddToPipelineInput(BaseModel):
    parcel: str = Field(description="Parcel number or Philadelphia street address.")
    stage: DealStage | None = Field(
        default=None,
        description=(
            "Which stage to file it under. Defaults to lead, which is where a lot you have "
            "just found belongs."
        ),
    )
    note: str | None = Field(default=None, max_length=1000, description="A note for the deal.")


@tool(
    name="add_to_pipeline",
    description=(
        "Put a lot in this buyer's pipeline so it is tracked. Safe to call more than once for "
        "the same lot — it will not duplicate. This changes their data; say what you added."
    ),
    input_model=AddToPipelineInput,
)
async def add_to_pipeline_tool(
    session: AsyncSession, context: ToolContext, payload: AddToPipelineInput
) -> ToolResult:
    from lotscope.pipeline.schemas import DealCreate
    from lotscope.pipeline.service import add_deal

    row = await _resolve(session, payload.parcel)
    if row is None:
        return empty(f"No Philadelphia parcel matches {payload.parcel!r}.")

    fields: dict[str, Any] = {"parcel_number": row.parcel_number}
    if payload.stage:
        fields["stage"] = payload.stage
    if payload.note:
        fields["note"] = payload.note
    try:
        create = DealCreate.model_validate(fields)
    except Exception as cause:
        return empty(f"That deal could not be created: {cause}")

    deal = await add_deal(session, context.user_id, create, limit=None)
    if deal.agent_run_id is None:
        deal.agent_run_id = context.agent_run_id
    await session.flush()

    return ToolResult(
        data={
            "deal_id": deal.id,
            "parcel_number": deal.parcel_number,
            "address": row.address,
            "stage": deal.stage,
            "added_by_run": context.agent_run_id,
        },
        sources=[_computed("lotscope_pipeline")],
        unverified=[],
    )


class UpdateDealInput(BaseModel):
    deal_id: int = Field(description="The pipeline deal to change.")
    stage: DealStage | None = Field(default=None, description="Move it to this stage.")
    note: str | None = Field(default=None, max_length=1000)
    offer_price: float | None = Field(default=None, ge=0)


@tool(
    name="update_deal",
    description="Change a deal already in this buyer's pipeline: its stage, note or offer price.",
    input_model=UpdateDealInput,
)
async def update_deal_tool(
    session: AsyncSession, context: ToolContext, payload: UpdateDealInput
) -> ToolResult:
    from lotscope.pipeline.models import Deal
    from lotscope.pipeline.schemas import DealUpdate
    from lotscope.pipeline.service import update_deal

    deal = await session.get(Deal, payload.deal_id)
    if deal is None or deal.user_id != context.user_id:
        return empty(f"Deal {payload.deal_id} is not in this buyer's pipeline.")

    changes = payload.model_dump(exclude_none=True, exclude={"deal_id"})
    if not changes:
        return empty("No fields were given to change.")
    try:
        update = DealUpdate.model_validate(changes)
    except Exception as cause:
        return empty(f"That change did not validate: {cause}")

    updated = await update_deal(session, context.user_id, deal.parcel_number, update)
    return ToolResult(
        data={
            "deal_id": payload.deal_id,
            "parcel_number": deal.parcel_number,
            "changed": changes,
            "stage": updated.stage if updated else deal.stage,
        },
        sources=[_computed("lotscope_pipeline")],
        unverified=[],
    )


class NoInput(BaseModel):
    pass


@tool(
    name="list_pipeline",
    description="Everything currently in this buyer's pipeline, with stage and last activity.",
    input_model=NoInput,
)
async def list_pipeline_tool(
    session: AsyncSession, context: ToolContext, payload: NoInput
) -> ToolResult:
    from lotscope.pipeline.service import list_deals

    deals = await list_deals(session, context.user_id)
    return ToolResult(
        data={"count": len(deals), "deals": [deal.model_dump(mode="json") for deal in deals]},
        sources=[_computed("lotscope_pipeline")],
        unverified=[] if deals else ["This buyer's pipeline is empty."],
    )


class WatchInput(BaseModel):
    parcel: str = Field(description="Parcel number or Philadelphia street address to watch.")
    note: str | None = Field(default=None, max_length=500)


@tool(
    name="watch",
    description=(
        "Add a lot to this buyer's saved list so changes to it reach them. Safe to call twice."
    ),
    input_model=WatchInput,
)
async def watch_tool(
    session: AsyncSession, context: ToolContext, payload: WatchInput
) -> ToolResult:
    from lotscope.watchlist.schemas import SavedParcelCreate
    from lotscope.watchlist.service import add_saved

    row = await _resolve(session, payload.parcel)
    if row is None:
        return empty(f"No Philadelphia parcel matches {payload.parcel!r}.")

    fields: dict[str, Any] = {"parcel_number": row.parcel_number}
    if payload.note:
        fields["note"] = payload.note
    saved = await add_saved(
        session, context.user_id, SavedParcelCreate.model_validate(fields), limit=None
    )
    if saved.agent_run_id is None:
        saved.agent_run_id = context.agent_run_id
    await session.flush()

    return ToolResult(
        data={
            "parcel_number": row.parcel_number,
            "address": row.address,
            "watching": True,
            "added_by_run": context.agent_run_id,
        },
        sources=[_computed("lotscope_watchlist")],
        unverified=[],
    )


@tool(
    name="unwatch",
    description=(
        "Take a lot off this buyer's saved list so changes to it stop reaching them. Safe to "
        "call on a lot that was never saved — it reports that rather than failing."
    ),
    input_model=WatchInput,
)
async def unwatch_tool(
    session: AsyncSession, context: ToolContext, payload: WatchInput
) -> ToolResult:
    from lotscope.watchlist.service import remove_saved

    row = await _resolve(session, payload.parcel)
    if row is None:
        return empty(f"No Philadelphia parcel matches {payload.parcel!r}.")

    removed = await remove_saved(session, context.user_id, row.parcel_number)
    return ToolResult(
        data={"parcel_number": row.parcel_number, "watching": False, "was_watching": removed},
        sources=[_computed("lotscope_watchlist")],
        unverified=[] if removed else [f"{row.parcel_number} was not on the saved list."],
    )


def _document_dir() -> Path:
    from lotscope.core.config import get_settings

    directory = Path(get_settings().agent_document_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


class DraftLoiInput(BaseModel):
    parcel: str = Field(description="Parcel number or Philadelphia street address.")
    price: float = Field(ge=0, description="The offer price in dollars.")
    all_cash: bool = Field(default=True, description="Whether the offer is all cash.")
    close_days: int = Field(default=30, ge=1, le=365, description="Days to close.")
    inspection_days: int = Field(default=10, ge=0, le=180, description="Inspection period.")
    earnest_money: float = Field(default=1000.0, ge=0, description="Deposit in dollars.")


@tool(
    name="draft_loi",
    description=(
        "Draft a letter of intent for a lot at a price and return the PDF path. This writes a "
        "draft only — nothing is sent to anyone. Tell the buyer where the file is and that "
        "they send it themselves."
    ),
    input_model=DraftLoiInput,
)
async def draft_loi_tool(
    session: AsyncSession, context: ToolContext, payload: DraftLoiInput
) -> ToolResult:
    from lotscope.accounts.models import User
    from lotscope.pipeline.schemas import OfferRequest
    from lotscope.pipeline.service import generate_offer
    from lotscope.reports.loi import LoiSigner

    row = await _resolve(session, payload.parcel)
    if row is None:
        return empty(f"No Philadelphia parcel matches {payload.parcel!r}.")

    user = await session.get(User, context.user_id)
    signer = LoiSigner(
        entity_name=getattr(user, "entity_name", None),
        signer_name=getattr(user, "signer_name", None) or getattr(user, "full_name", None),
        signer_phone=getattr(user, "signer_phone", None),
        signer_email=user.email if user else None,
    )
    request = OfferRequest(
        offer_price=payload.price,
        all_cash=payload.all_cash,
        close_days=payload.close_days,
        inspection_days=payload.inspection_days,
        earnest_money=payload.earnest_money,
    )
    pdf, filename = await generate_offer(
        session,
        context.user_id,
        row.parcel_number,
        request,
        default_signer=signer,
        now=datetime.now(UTC),
    )
    path = _document_dir() / filename
    path.write_bytes(pdf)

    return ToolResult(
        data={
            "parcel_number": row.parcel_number,
            "address": row.address,
            "offer_price": payload.price,
            "pdf_path": str(path),
            "sent": False,
        },
        sources=[_computed("lotscope_loi")],
        unverified=[
            "This is a draft. LotScope did not send it, and sending it is the buyer's decision."
        ],
    )


class DraftLetterInput(BaseModel):
    parcel: str | None = Field(default=None, description="The lot the letter is about.")
    owner_key: str | None = Field(default=None, description="A normalised owner name instead.")
    purpose: str = Field(
        default="acquisition",
        max_length=60,
        description="Why you are writing, such as 'acquisition' or 'introduction'.",
    )
    body: str | None = Field(
        default=None,
        max_length=4000,
        description="The letter text. Write it yourself; keep it plain and factual.",
    )


@tool(
    name="draft_letter",
    description=(
        "Draft an owner letter and return the PDF path. Never sends anything — LotScope has no "
        "way to post mail. Say it is a draft and where the file is."
    ),
    input_model=DraftLetterInput,
)
async def draft_letter_tool(
    session: AsyncSession, context: ToolContext, payload: DraftLetterInput
) -> ToolResult:
    from lotscope.accounts.models import User
    from lotscope.core.config import get_settings
    from lotscope.reports.mailer import Letter, letters_filename, render_letters_pdf

    if payload.parcel:
        row = await _resolve(session, payload.parcel)
        if row is None:
            return empty(f"No Philadelphia parcel matches {payload.parcel!r}.")
        owner = row.owner
        mailing = await session.scalar(
            text("SELECT mailing_address FROM parcel WHERE parcel_number = :p"),
            {"p": row.parcel_number},
        )
        subject = row.parcel_number
    elif payload.owner_key:
        found = (
            (
                await session.execute(
                    text(
                        "SELECT owner, mailing_address FROM parcel WHERE owner_key = :k "
                        "AND mailing_address IS NOT NULL LIMIT 1"
                    ),
                    {"k": payload.owner_key},
                )
            )
            .mappings()
            .one_or_none()
        )
        if found is None:
            return empty(f"No parcel is recorded under owner key {payload.owner_key!r}.")
        owner, mailing, subject = found["owner"], found["mailing_address"], payload.owner_key
    else:
        return empty("Give either a parcel or an owner key.")

    if not mailing:
        return empty(f"No mailing address is on record for {subject}, so no letter can be posted.")

    settings = get_settings()
    user = await session.get(User, context.user_id)
    pdf = render_letters_pdf(
        sender_name=(getattr(user, "full_name", None) or "A LotScope user") if user else "A buyer",
        sender_contact=user.email if user else "",
        letters=[
            Letter(
                owner=owner or "Property owner",
                mailing_address=mailing,
                body=payload.body
                or (
                    f"I am writing about {subject}. I buy vacant land in Philadelphia and would "
                    "like to talk about this parcel."
                ),
            )
        ],
        generated_at=datetime.now(UTC),
        disclaimer=settings.company_postal_address,
    )
    path = _document_dir() / letters_filename()
    path.write_bytes(pdf)

    return ToolResult(
        data={
            "subject": subject,
            "purpose": payload.purpose,
            "recipient_on_record": bool(mailing),
            "pdf_path": str(path),
            "sent": False,
        },
        sources=[_computed("lotscope_outreach")],
        unverified=[
            "This is a draft and was not sent. LotScope does not post mail.",
            "Direct mail is subject to CAN-SPAM and Fair Housing rules; the buyer is the sender.",
        ],
    )


class CreateAlertInput(BaseModel):
    kind: Literal[
        "sale_status", "new_violation", "new_delinquency", "neighbor_deed", "zba_filing"
    ] = Field(description="What change should reach this buyer.")
    scope: Literal["parcel", "area", "owned_neighbors"] = Field(
        description="Whether to watch one parcel, an area, or the neighbours of what they own."
    )
    parcel: str | None = Field(default=None, description="Required when scope is 'parcel'.")
    center_lat: float | None = None
    center_lng: float | None = None
    radius_m: float | None = Field(default=None, ge=10, le=5000)


@tool(
    name="create_alert",
    description=(
        "Stand a watch up so a change reaches this buyer without them asking: a sale status "
        "moving, a new violation, a new delinquency, a neighbour's deed, or a ZBA filing. "
        "Persisted and checked after each nightly ingest."
    ),
    input_model=CreateAlertInput,
)
async def create_alert_tool(
    session: AsyncSession, context: ToolContext, payload: CreateAlertInput
) -> ToolResult:
    target: dict[str, Any] = {}
    if payload.scope == "parcel":
        if not payload.parcel:
            return empty("A parcel-scoped alert needs a parcel.")
        row = await _resolve(session, payload.parcel)
        if row is None:
            return empty(f"No Philadelphia parcel matches {payload.parcel!r}.")
        target = {"parcel_number": row.parcel_number, "address": row.address}
    elif payload.scope == "area":
        if payload.center_lat is None or payload.center_lng is None:
            return empty("An area alert needs a centre point and a radius.")
        target = {
            "center_lat": payload.center_lat,
            "center_lng": payload.center_lng,
            "radius_m": payload.radius_m or 500.0,
        }
    else:
        target = {"owned_parcels": list(context.owned_parcels)}
        if not context.owned_parcels:
            return empty(
                "This buyer has recorded no parcels of their own, so there are no neighbours "
                "to watch."
            )

    existing = (
        await session.execute(
            select(AgentAlert).where(
                AgentAlert.user_id == context.user_id,
                AgentAlert.kind == payload.kind,
                AgentAlert.scope == payload.scope,
                AgentAlert.target == target,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return ToolResult(
            data={"alert_id": existing.id, "kind": payload.kind, "already_existed": True},
            sources=[_computed("lotscope_alerts")],
            unverified=[],
        )

    alert = AgentAlert(
        user_id=context.user_id,
        kind=payload.kind,
        scope=payload.scope,
        target=target,
        agent_run_id=context.agent_run_id,
    )
    session.add(alert)
    await session.flush()

    return ToolResult(
        data={
            "alert_id": alert.id,
            "kind": payload.kind,
            "scope": payload.scope,
            "target": target,
            "created_by_run": context.agent_run_id,
        },
        sources=[_computed("lotscope_alerts")],
        unverified=[
            "Alerts fire after the nightly ingest, so a change is seen the morning after it "
            "is published, not in real time."
        ],
    )


class ExportCsvInput(BaseModel):
    parcel_numbers: list[str] = Field(
        max_length=MAX_SCREEN_PARCELS, description="The lots to export."
    )
    columns: list[str] | None = Field(
        default=None,
        description=(
            "Columns to include. Defaults to address, zoning, lot area, vacancy, market value "
            "and the computed offer."
        ),
    )


DEFAULT_EXPORT_COLUMNS = (
    "parcel_number",
    "address",
    "base_zoning_code",
    "lot_area_sqft",
    "is_vacant",
    "market_value",
    "max_allowable_offer",
)


@tool(
    name="export_csv",
    description=(
        "Write a CSV of the lots you name and return the file path, so the buyer can open it "
        "in a spreadsheet. Nothing is emailed."
    ),
    input_model=ExportCsvInput,
)
async def export_csv_tool(
    session: AsyncSession, context: ToolContext, payload: ExportCsvInput
) -> ToolResult:
    import csv

    if not payload.parcel_numbers:
        return empty("No parcels were given to export.")

    requested = [
        column
        for column in (payload.columns or DEFAULT_EXPORT_COLUMNS)
        if column in DEFAULT_EXPORT_COLUMNS
    ] or list(DEFAULT_EXPORT_COLUMNS)

    rows = (
        (
            await session.execute(
                text(
                    "SELECT p.parcel_number, p.address, p.base_zoning_code, p.lot_area_sqft, "
                    "p.is_vacant, p.market_value, v.max_allowable_offer "
                    "FROM parcel p LEFT JOIN parcel_verdict v USING (parcel_number) "
                    "WHERE p.parcel_number = ANY(:parcels) ORDER BY p.parcel_number"
                ),
                {"parcels": payload.parcel_numbers[:MAX_SCREEN_PARCELS]},
            )
        )
        .mappings()
        .all()
    )

    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    path = _document_dir() / f"lotscope-export-{stamp}.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=requested, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row[column] for column in requested})

    missing = set(payload.parcel_numbers) - {row["parcel_number"] for row in rows}
    return ToolResult(
        data={
            "path": str(path),
            "rows": len(rows),
            "columns": requested,
            "requested": len(payload.parcel_numbers),
        },
        sources=[
            _computed("lotscope_export"),
            Source(name="opa_properties_public", url=urls.OPA_URL),
        ],
        unverified=(
            [f"{len(missing)} of the parcels asked for are not in the parcel table."]
            if missing
            else []
        ),
    )
