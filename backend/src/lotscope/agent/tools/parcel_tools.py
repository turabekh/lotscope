from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.agent.envelope import Source, ToolResult, empty
from lotscope.agent.tools.registry import ToolContext, tool
from lotscope.core.market import MARKET_CODE
from lotscope.packet.compose import LI_URL, OPA_URL, RTT_URL, TAX_URL, ZONING_URL
from lotscope.parcels.service import get_parcel_detail
from lotscope.search.schemas import AreaSearchRequest
from lotscope.search.spatial import search_area

_RESOLVE_SQL = text(
    "SELECT parcel_number FROM parcel "
    "WHERE market_code = :market_code AND ("
    "  lower(parcel_number) = lower(:needle) "
    "  OR lower(address) = lower(:needle) "
    "  OR address ILIKE :prefix"
    ") ORDER BY (lower(address) = lower(:needle)) DESC, parcel_number LIMIT 1"
)

_FRESHNESS_SQL = text(
    "SELECT dataset, last_success_at FROM dataset_freshness WHERE market_code = :market_code"
)


class GetParcelInput(BaseModel):
    parcel_number: str | None = Field(
        default=None,
        description="An OPA parcel number such as phl:282038200. Use this when you have it.",
    )
    address: str | None = Field(
        default=None,
        description=(
            "A Philadelphia street address such as '2138 N Fairhill St'. Use this when the "
            "buyer names a place rather than a parcel."
        ),
    )


class SearchAreaInput(BaseModel):
    center_lat: float | None = Field(
        default=None, description="Latitude of the centre of the area to search."
    )
    center_lng: float | None = Field(
        default=None, description="Longitude of the centre of the area to search."
    )
    radius_m: float | None = Field(
        default=None, ge=10, le=5000, description="Search radius in metres, up to 5000."
    )
    polygon: list[list[float]] | None = Field(
        default=None,
        description=(
            "A ring of [longitude, latitude] pairs bounding the search. Use this instead of "
            "centre and radius when the buyer describes a shape or a block."
        ),
    )
    vacant_only: bool = Field(
        default=True, description="Restrict to vacant land, which is what this buyer buys."
    )
    scheduled_for_sale: bool | None = Field(
        default=None,
        description="True to return only lots scheduled for a future sheriff-sale auction.",
    )
    min_lot_sqft: int | None = Field(
        default=None,
        description=(
            "Smallest lot to return. Leave unset to inherit the buyer's own floor from "
            "their buy box."
        ),
    )
    limit: int = Field(default=25, ge=1, le=100, description="How many lots to return.")


async def _freshness(session: AsyncSession) -> dict[str, datetime]:
    rows = await session.execute(_FRESHNESS_SQL, {"market_code": MARKET_CODE})
    return {row.dataset: row.last_success_at for row in rows if row.last_success_at}


def _sources(fetched: dict[str, datetime], names: list[tuple[str, str, str]]) -> list[Source]:
    return [
        Source(name=label, url=url, fetched_at=fetched.get(dataset))
        for label, url, dataset in names
    ]


@tool(
    name="get_parcel",
    description=(
        "Look up one Philadelphia parcel by parcel number or street address and return what "
        "LotScope knows about it: owner and mailing address, lot size, zoning district, "
        "whether it reads as vacant, assessed value, tax delinquency, open L&I violations, "
        "any scheduled sheriff sale, and the computed verdict — what can be built by right "
        "and the maximum allowable offer. The verdict is computed when you ask, not read "
        "from a stale table. Use this before saying anything specific about a lot."
    ),
    input_model=GetParcelInput,
)
async def get_parcel(
    session: AsyncSession, context: ToolContext, payload: GetParcelInput
) -> ToolResult:
    needle = (payload.parcel_number or payload.address or "").strip()
    if not needle:
        return empty("No parcel number or address was given, so nothing could be looked up.")

    parcel_number = await session.scalar(
        _RESOLVE_SQL,
        {"market_code": MARKET_CODE, "needle": needle, "prefix": f"{needle}%"},
    )
    if parcel_number is None:
        return empty(f"No Philadelphia parcel matches {needle!r} in the parcel table.")

    detail = await get_parcel_detail(session, parcel_number)
    if detail is None:
        return empty(f"Parcel {parcel_number} resolved but no detail could be assembled.")

    from lotscope.verdict.service import compute_verdict

    verdict = await compute_verdict(session, parcel_number)
    fetched = await _freshness(session)

    data: dict[str, Any] = {
        "parcel_number": parcel_number,
        "detail": detail.model_dump(mode="json"),
        "verdict": verdict.model_dump(mode="json") if verdict is not None else None,
        "computed_at": datetime.now(UTC).isoformat(),
    }

    unverified: list[str] = [
        "Water and sewer liens and PGW balances are not in any dataset LotScope holds.",
    ]
    if verdict is None:
        unverified.append(
            f"No verdict could be computed for {parcel_number}, so there is no offer figure."
        )

    return ToolResult(
        data=data,
        sources=_sources(
            fetched,
            [
                ("opa_properties_public", OPA_URL, "opa_properties_public"),
                ("rtt_summary", RTT_URL, "rtt_summary"),
                ("li_event", LI_URL, "violations"),
                ("tax_status", TAX_URL, "real_estate_tax_delinquencies"),
                ("zoning_base_districts", ZONING_URL, "zoning_base_districts"),
            ],
        ),
        unverified=unverified,
    )


@tool(
    name="search_area",
    description=(
        "Find Philadelphia lots inside an area, either a centre point with a radius or a "
        "polygon. Filters default to this buyer's own buy box, so an unfiltered call already "
        "screens to what they buy. Returns each lot with its address, zoning, lot size and "
        "opportunity score. Use this when the buyer asks what is available somewhere, rather "
        "than about one lot they already named."
    ),
    input_model=SearchAreaInput,
)
async def search_area_tool(
    session: AsyncSession, context: ToolContext, payload: SearchAreaInput
) -> ToolResult:
    buy_box = context.buy_box or {}
    min_lot = payload.min_lot_sqft
    if min_lot is None:
        min_lot = buy_box.get("min_lot_sqft")

    request_kwargs: dict[str, Any] = {
        "market": MARKET_CODE,
        "vacant_only": payload.vacant_only,
        "limit": payload.limit,
    }
    if payload.polygon:
        request_kwargs["polygon"] = {
            "type": "Polygon",
            "coordinates": [payload.polygon],
        }
    elif payload.center_lat is not None and payload.center_lng is not None:
        request_kwargs["center"] = {"lat": payload.center_lat, "lng": payload.center_lng}
        request_kwargs["radius_m"] = payload.radius_m or 500.0
    else:
        return empty("No area was given: supply either a centre with a radius, or a polygon ring.")
    if min_lot is not None:
        request_kwargs["min_lot_area_sqft"] = float(min_lot)
    if payload.scheduled_for_sale is not None:
        request_kwargs["scheduled_for_sale"] = bool(payload.scheduled_for_sale)

    try:
        request = AreaSearchRequest.model_validate(request_kwargs)
    except Exception as cause:
        return empty(f"The area could not be read: {cause}")

    results, total = await search_area(session, request)
    fetched = await _freshness(session)

    applied = {
        "vacant_only": payload.vacant_only,
        "min_lot_sqft": min_lot,
        "scheduled_for_sale": payload.scheduled_for_sale,
        "limit": payload.limit,
        "min_lot_sqft_came_from_buy_box": payload.min_lot_sqft is None and min_lot is not None,
    }

    unverified: list[str] = []
    if total > len(results):
        unverified.append(
            f"{total} lots matched but only {len(results)} were returned; the rest are unseen."
        )
    if not buy_box:
        unverified.append(
            "This buyer has no saved buy box, so nothing was screened against their numbers."
        )

    return ToolResult(
        data={
            "count": len(results),
            "total": total,
            "filters_applied": applied,
            "results": [result.model_dump(mode="json") for result in results],
        },
        sources=_sources(
            fetched,
            [
                ("opa_properties_public", OPA_URL, "opa_properties_public"),
                ("zoning_base_districts", ZONING_URL, "zoning_base_districts"),
            ],
        ),
        unverified=unverified,
    )
