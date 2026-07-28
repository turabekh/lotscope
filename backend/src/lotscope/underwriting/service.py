from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.errors import ConflictError, NotFoundError
from lotscope.underwriting.models import UnderwritingProfile
from lotscope.underwriting.schemas import ProfileRead, ProfileWrite


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
