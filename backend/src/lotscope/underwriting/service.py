from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.errors import ConflictError, NotFoundError
from lotscope.underwriting.matching import match_conditions
from lotscope.underwriting.models import UnderwritingProfile
from lotscope.underwriting.schemas import (
    BuyBox,
    BuyBoxMatch,
    BuyBoxMatches,
    ProfileRead,
    ProfileWrite,
)

_MATCH_FROM = "FROM parcel_verdict v JOIN parcel p USING (parcel_number)"
_MATCH_COUNT_SQL = f"SELECT count(*) {_MATCH_FROM}"
_MATCH_ORDER_SQL = "ORDER BY v.opportunity_score DESC NULLS LAST, v.parcel_number LIMIT :limit"
_MATCH_SELECT_SQL = (
    "SELECT v.parcel_number, p.address, v.opportunity_score, v.max_allowable_offer, "
    f"v.est_margin, v.by_right_units, v.risk_score {_MATCH_FROM}"
)


async def _owned(session: AsyncSession, profile_id: int, owner_id: int) -> UnderwritingProfile:
    profile = await session.get(UnderwritingProfile, profile_id)
    if profile is None or profile.owner_id != owner_id:
        raise NotFoundError(f"Underwriting profile {profile_id} was not found.")
    return profile


async def _clear_other_defaults(session: AsyncSession, owner_id: int, keep_id: int | None) -> None:
    statement = (
        update(UnderwritingProfile)
        .where(UnderwritingProfile.owner_id == owner_id, UnderwritingProfile.is_default.is_(True))
        .values(is_default=False)
    )
    if keep_id is not None:
        statement = statement.where(UnderwritingProfile.id != keep_id)
    await session.execute(statement)


async def list_profiles(session: AsyncSession, owner_id: int) -> list[ProfileRead]:
    rows = (
        await session.execute(
            select(UnderwritingProfile)
            .where(UnderwritingProfile.owner_id == owner_id)
            .order_by(UnderwritingProfile.is_default.desc(), UnderwritingProfile.name)
        )
    ).scalars()
    return [ProfileRead.model_validate(row) for row in rows]


async def get_profile(session: AsyncSession, profile_id: int, owner_id: int) -> ProfileRead:
    return ProfileRead.model_validate(await _owned(session, profile_id, owner_id))


async def create_profile(
    session: AsyncSession, owner_id: int, request: ProfileWrite
) -> ProfileRead:
    profile = UnderwritingProfile(
        owner_id=owner_id,
        name=request.name,
        is_default=request.is_default,
        version=1,
        assumptions=dict(request.assumptions),
        buy_box=request.buy_box.model_dump(),
    )
    session.add(profile)
    try:
        await session.flush()
    except IntegrityError as error:
        raise ConflictError(f"A profile named {request.name!r} already exists.") from error
    if request.is_default:
        await _clear_other_defaults(session, owner_id, profile.id)
    return ProfileRead.model_validate(profile)


async def update_profile(
    session: AsyncSession, profile_id: int, owner_id: int, request: ProfileWrite
) -> ProfileRead:
    profile = await _owned(session, profile_id, owner_id)
    profile.name = request.name
    profile.is_default = request.is_default
    profile.assumptions = dict(request.assumptions)
    profile.buy_box = request.buy_box.model_dump()
    profile.version += 1
    try:
        await session.flush()
    except IntegrityError as error:
        raise ConflictError(f"A profile named {request.name!r} already exists.") from error
    if request.is_default:
        await _clear_other_defaults(session, owner_id, profile.id)
    await session.refresh(profile)
    return ProfileRead.model_validate(profile)


async def delete_profile(session: AsyncSession, profile_id: int, owner_id: int) -> None:
    profile = await _owned(session, profile_id, owner_id)
    await session.delete(profile)
    await session.flush()


async def default_assumptions(session: AsyncSession, owner_id: int) -> dict[str, float]:
    profile = (
        await session.execute(
            select(UnderwritingProfile).where(
                UnderwritingProfile.owner_id == owner_id,
                UnderwritingProfile.is_default.is_(True),
            )
        )
    ).scalar_one_or_none()
    return dict(profile.assumptions) if profile is not None else {}


async def default_buy_box(session: AsyncSession, owner_id: int) -> BuyBox | None:
    profile = (
        await session.execute(
            select(UnderwritingProfile).where(
                UnderwritingProfile.owner_id == owner_id,
                UnderwritingProfile.is_default.is_(True),
            )
        )
    ).scalar_one_or_none()
    return BuyBox.model_validate(profile.buy_box) if profile is not None else None


async def find_buy_box_matches(
    session: AsyncSession, owner_id: int, *, market: str, limit: int
) -> BuyBoxMatches:
    buy_box = await default_buy_box(session, owner_id)
    if buy_box is None:
        return BuyBoxMatches(
            market=market, total=0, matches=[], criteria_applied=[], has_profile=False
        )

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
        has_profile=True,
    )
