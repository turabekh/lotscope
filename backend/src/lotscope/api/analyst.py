from collections.abc import AsyncIterator
from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.accounts.models import User
from lotscope.agent.client import AnthropicToolClient
from lotscope.agent.models import AgentConversation, AgentRun, AgentStep
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
from lotscope.budget.service import (
    CHAT_SOURCE,
    check_analyst_budget,
    maybe_alert_global_budget,
    record_analyst_usage,
)
from lotscope.buybox.service import read_buy_box
from lotscope.core.config import Settings
from lotscope.core.errors import ConfigurationError, NotFoundError, QuotaExceededError
from lotscope.notifications.email import get_email_sender

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
    verdict = await check_analyst_budget(session, user, settings)
    if not verdict.allowed:
        # 429 rather than 402: nothing is for sale here, the day's allowance is spent.
        raise QuotaExceededError(verdict.message)
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

    async def spend_guard(input_tokens: int, output_tokens: int) -> str | None:
        """Asked before every model call, with what this run has spent so far."""
        async with factory() as guard_session:
            live_user = await guard_session.get(User, user.id)
            if live_user is None:
                return None
            verdict = await check_analyst_budget(
                guard_session,
                live_user,
                settings,
                pending_input_tokens=input_tokens,
                pending_output_tokens=output_tokens,
                model=settings.analyst_model,
            )
        return None if verdict.allowed else verdict.message

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
                spend_guard=spend_guard,
            ):
                yield event
            # The ledger is written whatever the run did. A run that failed or was
            # cancelled still burned the tokens it burned, and a ceiling that only
            # counts successes is a ceiling a failing loop never reaches.
            await record_analyst_usage(
                run_session,
                user_id=user.id,
                model=live.model,
                input_tokens=live.input_tokens,
                output_tokens=live.output_tokens,
                source=CHAT_SOURCE,
            )
            await run_session.commit()
        async with factory() as alert_session:
            await maybe_alert_global_budget(alert_session, get_email_sender(settings), settings)
            await alert_session.commit()

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


class ConversationRead(BaseModel):
    id: int
    title: str | None
    updated_at: datetime
    run_count: int


class ThreadStep(BaseModel):
    """One step of a run, as the thread renders it."""

    sequence: int
    kind: str
    text: str | None = None
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    envelope: dict[str, Any] | None = None
    duration_ms: int | None = None


class ThreadTurn(BaseModel):
    run_id: int
    question: str
    answer: str | None
    status: str
    created_at: datetime
    steps: list[ThreadStep] = []


class ThreadRead(BaseModel):
    conversation_id: int
    title: str | None
    turns: list[ThreadTurn] = []


class OpeningRead(BaseModel):
    """What the Analyst says before the buyer has said anything.

    Server-side on purpose: what it opens with depends on whether a buy box exists and
    when the next sale is, and neither belongs in client copy.
    """

    text: str
    needs_buy_box: bool
    suggested_prompt: str | None = None
    next_sale_date: date | None = None


@router.get("/conversations", response_model=list[ConversationRead])
async def list_conversations(
    session: SessionDep, user: CurrentUserDep, limit: int = 40
) -> list[ConversationRead]:
    rows = (
        (
            await session.execute(
                text(
                    "SELECT c.id, c.title, c.updated_at, count(r.id) AS run_count "
                    "FROM agent_conversation c LEFT JOIN agent_run r ON r.conversation_id = c.id "
                    "WHERE c.user_id = :u GROUP BY c.id, c.title, c.updated_at "
                    "ORDER BY c.updated_at DESC LIMIT :limit"
                ),
                {"u": user.id, "limit": limit},
            )
        )
        .mappings()
        .all()
    )
    return [ConversationRead.model_validate(dict(row)) for row in rows]


@router.get("/conversations/{conversation_id}", response_model=ThreadRead)
async def read_thread(
    conversation_id: int, session: SessionDep, user: CurrentUserDep
) -> ThreadRead:
    conversation = (
        await session.execute(
            select(AgentConversation).where(
                AgentConversation.id == conversation_id, AgentConversation.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if conversation is None:
        raise NotFoundError(f"Conversation {conversation_id} was not found.")

    runs = list(
        (
            await session.execute(
                select(AgentRun)
                .where(AgentRun.conversation_id == conversation_id)
                .order_by(AgentRun.id)
            )
        )
        .scalars()
        .all()
    )
    steps_by_run: dict[int, list[AgentStep]] = {}
    if runs:
        for step in (
            (
                await session.execute(
                    select(AgentStep)
                    .where(AgentStep.run_id.in_([run.id for run in runs]))
                    .order_by(AgentStep.run_id, AgentStep.sequence)
                )
            )
            .scalars()
            .all()
        ):
            steps_by_run.setdefault(step.run_id, []).append(step)

    return ThreadRead(
        conversation_id=conversation.id,
        title=conversation.title,
        turns=[
            ThreadTurn(
                run_id=run.id,
                question=run.question,
                answer=run.answer,
                status=run.status,
                created_at=run.created_at,
                steps=[
                    ThreadStep(
                        sequence=step.sequence,
                        kind=step.kind,
                        text=step.text,
                        tool_name=step.tool_name,
                        tool_input=step.tool_input,
                        envelope=step.envelope,
                        duration_ms=step.duration_ms,
                    )
                    for step in steps_by_run.get(run.id, [])
                ],
            )
            for run in runs
        ],
    )


@router.get("/opening", response_model=OpeningRead)
async def opening(session: SessionDep, user: CurrentUserDep) -> OpeningRead:
    from lotscope.buybox.service import read_buy_box

    buy_box = await read_buy_box(session, user.id)
    configured = bool(buy_box.areas or buy_box.max_bid or buy_box.owned_parcels)

    next_sale = await session.scalar(
        text("SELECT min(sale_date) FROM sheriff_sale WHERE sale_date >= current_date")
    )

    if not configured:
        return OpeningRead(
            text=(
                "I work Philadelphia vacant land for you. Before I can screen anything I need "
                "your buy box: where you will buy, what you will pay, and what you are doing "
                "with the lot. Tell me in your own words and I will set it up."
            ),
            needs_buy_box=True,
            suggested_prompt="I buy vacant lots in ",
            next_sale_date=next_sale,
        )

    if next_sale is None:
        return OpeningRead(
            text=(
                "Your buy box is set. There is no sheriff sale on the calendar right now, so "
                "ask me about a lot and I will read the city's records live."
            ),
            needs_buy_box=False,
            suggested_prompt="What's the story on ",
            next_sale_date=None,
        )

    return OpeningRead(
        text=(
            f"Your buy box is set. The next sheriff sale is {next_sale.isoformat()}. I can "
            f"screen every vacant lot on it against your box and tell you which are worth "
            f"bidding on."
        ),
        needs_buy_box=False,
        suggested_prompt=f"Screen the {next_sale.isoformat()} sale against my buy box",
        next_sale_date=next_sale,
    )
