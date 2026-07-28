from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.api.deps import get_session, require_admin
from lotscope.policies.schemas import PolicyRead, PolicySummary, PolicyWrite
from lotscope.policies.service import get_policy, list_policies, publish_policy

router = APIRouter(tags=["policies"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
AdminDep = Annotated[User, Depends(require_admin)]


@router.get("/policies", response_model=list[PolicySummary])
async def read_policy_index(session: SessionDep) -> list[PolicySummary]:
    return await list_policies(session)


@router.get("/policies/{slug}", response_model=PolicyRead)
async def read_policy(slug: str, session: SessionDep) -> PolicyRead:
    return await get_policy(session, slug)


@router.put("/admin/policies/{slug}", response_model=PolicyRead)
async def publish_policy_document(
    slug: str, data: PolicyWrite, session: SessionDep, admin: AdminDep
) -> PolicyRead:
    policy = await publish_policy(session, slug, data)
    await session.commit()
    return policy
