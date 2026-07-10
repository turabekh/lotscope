from typing import Annotated

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.accounts.schemas import UserRead
from lotscope.admin.schemas import (
    AdminOverview,
    AdminUsersResponse,
    AdminUserUpdate,
    DatasetStatus,
    JobCatalogEntry,
    JobRunRequest,
    JobRunSummary,
)
from lotscope.admin.service import (
    enqueue_job,
    job_catalog,
    list_datasets,
    list_job_runs,
    list_users,
    platform_overview,
    update_user,
)
from lotscope.api.deps import get_arq_pool, get_session, require_admin

router = APIRouter(prefix="/admin", tags=["admin"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
AdminDep = Annotated[User, Depends(require_admin)]
ArqPoolDep = Annotated[ArqRedis, Depends(get_arq_pool)]


@router.get("/overview", response_model=AdminOverview)
async def admin_overview(session: SessionDep, admin: AdminDep) -> AdminOverview:
    return await platform_overview(session)


@router.get("/datasets", response_model=list[DatasetStatus])
async def admin_datasets(session: SessionDep, admin: AdminDep) -> list[DatasetStatus]:
    return await list_datasets(session)


@router.get("/users", response_model=AdminUsersResponse)
async def admin_users(
    session: SessionDep,
    admin: AdminDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminUsersResponse:
    return await list_users(session, limit=limit, offset=offset)


@router.patch("/users/{user_id}", response_model=UserRead)
async def admin_update_user(
    user_id: int, data: AdminUserUpdate, session: SessionDep, admin: AdminDep
) -> UserRead:
    result = await update_user(session, user_id, data)
    await session.commit()
    return result


@router.get("/jobs", response_model=list[JobCatalogEntry])
async def admin_jobs(session: SessionDep, admin: AdminDep) -> list[JobCatalogEntry]:
    return await job_catalog(session)


@router.get("/jobs/runs", response_model=list[JobRunSummary])
async def admin_job_runs(
    session: SessionDep,
    admin: AdminDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[JobRunSummary]:
    return await list_job_runs(session, limit=limit)


@router.post("/jobs/run", response_model=JobRunSummary)
async def admin_run_job(
    data: JobRunRequest, session: SessionDep, admin: AdminDep, pool: ArqPoolDep
) -> JobRunSummary:
    result = await enqueue_job(
        session, pool, job_id=data.job_id, triggered_by=admin.id, params=data.params
    )
    await session.commit()
    return result
