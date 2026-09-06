from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.buybox.service import read_buy_box
from lotscope.underwriting.matching import match_conditions
from lotscope.underwriting.schemas import BuyBoxMatch, BuyBoxMatches

_MATCH_FROM = "FROM parcel_screen v JOIN parcel p USING (parcel_number)"
_MATCH_COUNT_SQL = f"SELECT count(*) {_MATCH_FROM}"
_MATCH_ORDER_SQL = "ORDER BY v.opportunity_score DESC NULLS LAST, v.parcel_number LIMIT :limit"
_MATCH_SELECT_SQL = (
    "SELECT v.parcel_number, p.address, v.opportunity_score, v.max_allowable_offer, "
    f"v.est_margin, v.by_right_units, v.risk_score {_MATCH_FROM}"
)


async def find_buy_box_matches(
    session: AsyncSession, owner_id: int, *, market: str, limit: int
) -> BuyBoxMatches:
    buy_box = await read_buy_box(session, owner_id)

    conditions, params = match_conditions(buy_box)
    where = " AND ".join(["p.market_code = :market", "p.is_vacant IS TRUE", *conditions])
    params["market"] = market

    total = (await session.execute(text(f"{_MATCH_COUNT_SQL} WHERE {where}"), params)).scalar_one()

    rows = (
        await session.execute(
            text(f"{_MATCH_SELECT_SQL} WHERE {where} {_MATCH_ORDER_SQL}"),
            {**params, "limit": limit},
        )
    ).mappings()

    matches = [
        BuyBoxMatch(
            parcel_number=row["parcel_number"],
            address=row["address"],
            opportunity_score=row["opportunity_score"],
            max_allowable_offer=row["max_allowable_offer"],
            est_margin=row["est_margin"],
            by_right_units=row["by_right_units"],
            risk_score=row["risk_score"],
        )
        for row in rows
    ]
    return BuyBoxMatches(
        market=market,
        total=total,
        matches=matches,
        criteria_applied=sorted(params.keys() - {"market"}),
        has_profile=buy_box.is_configured,
    )
