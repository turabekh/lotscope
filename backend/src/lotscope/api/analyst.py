from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.accounts.models import User
from lotscope.agent.client import AnthropicToolClient
from lotscope.agent.models import AgentRun, AgentStep
from lotscope.agent.runtime import AgentEvent, create_run, ensure_conversation, run_agent
from lotscope.agent.stream import cancel_run, is_cancelled, sse
from lotscope.agent.tools.registry import ToolContext
from lotscope.api.deps import (
    get_app_settings,
    get_current_user,
    get_redis,
    get_session,
    get_session_factory,
)
from lotscope.buybox.service import read_buy_box
from lotscope.core.config import Settings
from lotscope.core.errors import ConfigurationError, NotFoundError

router = APIRouter(prefix="/analyst", tags=["analyst"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
FactoryDep = Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)]
RedisDep = Annotated[Redis, Depends(get_redis)]


class MessageRequest(BaseModel):
    conversation_id: int | None = None
    text: str = Field(min_length=1, max_length=4000)


class RunRead(BaseModel):
    run_id: int
    conversation_id: int
    status: str
    events_url: str


@router.post("/messages", response_model=RunRead, status_code=status.HTTP_202_ACCEPTED)
async def post_message(
    data: MessageRequest, session: SessionDep, user: CurrentUserDep, settings: SettingsDep
) -> RunRead:
    if not settings.anthropic_api_key:
        raise ConfigurationError("The analyst is not available: no model key is configured.")
    conversation = await ensure_conversation(session, user.id, data.conversation_id, data.text)
    run = await create_run(
        session,
        user_id=user.id,
        conversation=conversation,
        question=data.text,
        model=settings.analyst_model,
    )
    await session.commit()
    return RunRead(
        run_id=run.id,
        conversation_id=conversation.id,
        status=run.status,
        events_url=f"/analyst/runs/{run.id}/events",
    )


async def _owned_run(session: AsyncSession, run_id: int, user_id: int) -> AgentRun:
    run = (
        await session.execute(
            select(AgentRun).where(AgentRun.id == run_id, AgentRun.user_id == user_id)
        )
    ).scalar_one_or_none()
    if run is None:
        raise NotFoundError(f"Run {run_id} was not found.")
    return run


@router.get("/runs/{run_id}/events")
async def run_events(
    run_id: int,
    session: SessionDep,
    user: CurrentUserDep,
    settings: SettingsDep,
    factory: FactoryDep,
    redis: RedisDep,
) -> StreamingResponse:
    run = await _owned_run(session, run_id, user.id)
    buy_box = await read_buy_box(session, user.id)
    context = ToolContext(
        user_id=user.id,
        buy_box=buy_box.model_dump(mode="json"),
        owned_parcels=tuple(buy_box.owned_parcels),
        redis=redis,
    )
    client = AnthropicToolClient(settings)

    async def events() -> AsyncIterator[AgentEvent]:
        async with factory() as run_session:
            live = await run_session.get(AgentRun, run.id)
            if live is None:
                return
            async for event in run_agent(
                run_session,
                client,
                live,
                context=context,
                should_cancel=lambda: is_cancelled(run.id),
            ):
                yield event
            await run_session.commit()

    return StreamingResponse(
        sse(events()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/runs/{run_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
async def cancel(run_id: int, session: SessionDep, user: CurrentUserDep) -> dict[str, str]:
    await _owned_run(session, run_id, user.id)
    cancel_run(run_id)
    return {"status": "cancelling"}


class StepRead(BaseModel):
    sequence: int
    kind: str
    tool_name: str | None
    text: str | None
    duration_ms: int | None


@router.get("/runs/{run_id}/steps", response_model=list[StepRead])
async def run_steps(run_id: int, session: SessionDep, user: CurrentUserDep) -> list[StepRead]:
    await _owned_run(session, run_id, user.id)
    rows = (
        await session.execute(
            select(AgentStep).where(AgentStep.run_id == run_id).order_by(AgentStep.sequence)
        )
    ).scalars()
    return [
        StepRead(
            sequence=row.sequence,
            kind=row.kind,
            tool_name=row.tool_name,
            text=row.text,
            duration_ms=row.duration_ms,
        )
        for row in rows
    ]
