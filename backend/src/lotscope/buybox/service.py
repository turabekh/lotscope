from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.buybox.models import BuyBox
from lotscope.buybox.schemas import (
    MAX_OWNED_PARCELS,
    BuyBoxRead,
    BuyBoxWrite,
    OwnedParcelSeedResult,
)
from lotscope.core.errors import ValidationError
from lotscope.core.market import MARKET_CODE

OWNER_SOURCE = "opa_properties_public"
OWNER_SOURCE_URL = "https://opendataphilly.org/datasets/philadelphia-properties-and-assessments/"

_OWNER_MATCH_SQL = text(
    "SELECT parcel_number FROM parcel "
    "WHERE market_code = :market_code AND owner_key = :owner_key "
    "ORDER BY parcel_number LIMIT :limit"
)
_OWNER_KEY_SQL = text(
    "SELECT nullif(upper(btrim(regexp_replace(regexp_replace("
    ":owner, '[.,#]', '', 'g'), '\\s+', ' ', 'g'))), '')"
)
_FETCHED_AT_SQL = text(
    "SELECT last_success_at FROM dataset_freshness "
    "WHERE market_code = :market_code AND dataset = :dataset"
)


def _defaults(user_id: int) -> BuyBox:
    blank = BuyBoxWrite()
    return BuyBox(
        user_id=user_id,
        areas=[area.model_dump() for area in blank.areas],
        max_bid=blank.max_bid,
        target_use=blank.target_use,
        min_lot_sqft=blank.min_lot_sqft,
        zoning_codes=list(blank.zoning_codes),
        exclude_city_neighbor=blank.exclude_city_neighbor,
        exclude_open_violations=blank.exclude_open_violations,
        exclude_historic=blank.exclude_historic,
        exclude_flood=blank.exclude_flood,
        assumptions=dict(blank.assumptions),
        owned_parcels=list(blank.owned_parcels),
    )


async def _row(session: AsyncSession, user_id: int) -> BuyBox | None:
    return (
        await session.execute(select(BuyBox).where(BuyBox.user_id == user_id))
    ).scalar_one_or_none()


async def read_buy_box(session: AsyncSession, user_id: int) -> BuyBoxRead:
    row = await _row(session, user_id)
    if row is None:
        now = datetime.now(UTC)
        return BuyBoxRead.model_validate(
            {
                **BuyBoxWrite().model_dump(),
                "user_id": user_id,
                "created_at": now,
                "updated_at": now,
            }
        )
    return BuyBoxRead.model_validate(row)


async def write_buy_box(session: AsyncSession, user_id: int, data: BuyBoxWrite) -> BuyBoxRead:
    row = await _row(session, user_id)
    if row is None:
        row = _defaults(user_id)
        session.add(row)
    row.areas = [area.model_dump() for area in data.areas]
    row.max_bid = Decimal(str(data.max_bid)) if data.max_bid is not None else None
    row.target_use = data.target_use
    row.min_lot_sqft = data.min_lot_sqft
    row.zoning_codes = list(data.zoning_codes)
    row.exclude_city_neighbor = data.exclude_city_neighbor
    row.exclude_open_violations = data.exclude_open_violations
    row.exclude_historic = data.exclude_historic
    row.exclude_flood = data.exclude_flood
    row.assumptions = dict(data.assumptions)
    row.owned_parcels = list(data.owned_parcels)
    await session.flush()
    await session.refresh(row)
    return BuyBoxRead.model_validate(row)


async def buy_box_assumptions(session: AsyncSession, user_id: int | None) -> dict[str, float]:
    if user_id is None:
        return {}
    row = await _row(session, user_id)
    return dict(row.assumptions) if row is not None else {}


async def seed_owned_parcels(
    session: AsyncSession, user_id: int, owner_name: str
) -> OwnedParcelSeedResult:
    owner_key = await session.scalar(_OWNER_KEY_SQL, {"owner": owner_name.strip()})
    if not owner_key:
        raise ValidationError("An owner name is needed to seed owned parcels.")

    current = await read_buy_box(session, user_id)
    room = MAX_OWNED_PARCELS - len(current.owned_parcels)
    if room <= 0:
        raise ValidationError(
            f"A buy box holds at most {MAX_OWNED_PARCELS} owned parcels; remove some first."
        )

    found = (
        (
            await session.execute(
                _OWNER_MATCH_SQL,
                {"market_code": MARKET_CODE, "owner_key": owner_key, "limit": room},
            )
        )
        .scalars()
        .all()
    )
    added = [parcel for parcel in found if parcel not in set(current.owned_parcels)]
    if added:
        updated = BuyBoxWrite(
            **{
                **current.model_dump(exclude={"user_id", "created_at", "updated_at"}),
                "owned_parcels": [*current.owned_parcels, *added],
            }
        )
        current = await write_buy_box(session, user_id, updated)

    fetched_at = await session.scalar(
        _FETCHED_AT_SQL, {"market_code": MARKET_CODE, "dataset": OWNER_SOURCE}
    )
    return OwnedParcelSeedResult(
        owner_name=owner_name.strip(),
        added=added,
        owned_parcels=list(current.owned_parcels),
        source=OWNER_SOURCE,
        source_url=OWNER_SOURCE_URL,
        fetched_at=fetched_at or datetime.now(UTC),
    )
