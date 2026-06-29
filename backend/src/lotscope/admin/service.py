from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.accounts.schemas import UserRead
from lotscope.admin.schemas import (
    AdminOverview,
    AdminUsersResponse,
    AdminUserUpdate,
    DatasetStatus,
)
from lotscope.core.errors import NotFoundError
from lotscope.ingestion.models import DatasetFreshness

_COUNTS_SQL = text(
    "SELECT "
    "(SELECT count(*) FROM parcel) AS parcels_total, "
    "(SELECT count(*) FROM parcel WHERE coalesce(is_vacant, false)) AS parcels_vacant, "
    "(SELECT count(*) FROM parcel_verdict) AS verdicts_total, "
    "(SELECT count(*) FROM deed_document) AS deeds_total, "
    "(SELECT count(*) FROM saved_search) AS saved_searches_total, "
    "(SELECT count(*) FROM neighborhood) AS neighborhoods_total"
)


async def list_datasets(session: AsyncSession) -> list[DatasetStatus]:
    rows = (
        await session.execute(select(DatasetFreshness).order_by(DatasetFreshness.dataset))
    ).scalars()
    return [DatasetStatus.model_validate(row) for row in rows]


async def platform_overview(session: AsyncSession) -> AdminOverview:
    counts = (await session.execute(_COUNTS_SQL)).one()
    by_tier_rows = (
        await session.execute(select(User.tier, func.count()).group_by(User.tier))
    ).all()
    by_tier = {tier: int(count) for tier, count in by_tier_rows}
    return AdminOverview(
        users_total=sum(by_tier.values()),
        users_by_tier=by_tier,
        parcels_total=int(counts.parcels_total or 0),
        parcels_vacant=int(counts.parcels_vacant or 0),
        verdicts_total=int(counts.verdicts_total or 0),
        deeds_total=int(counts.deeds_total or 0),
        saved_searches_total=int(counts.saved_searches_total or 0),
        neighborhoods_total=int(counts.neighborhoods_total or 0),
    )


async def list_users(
    session: AsyncSession, *, limit: int = 50, offset: int = 0
) -> AdminUsersResponse:
    total = int(await session.scalar(select(func.count()).select_from(User)) or 0)
    rows = (
        await session.execute(
            select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
        )
    ).scalars()
    return AdminUsersResponse(total=total, users=[UserRead.model_validate(row) for row in rows])


async def update_user(session: AsyncSession, user_id: int, data: AdminUserUpdate) -> UserRead:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} was not found.")
    if data.role is not None:
        user.role = data.role
    if data.tier is not None:
        user.tier = data.tier
    if data.is_active is not None:
        user.is_active = data.is_active
    await session.flush()
    return UserRead.model_validate(user)
