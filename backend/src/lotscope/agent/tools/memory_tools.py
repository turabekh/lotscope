"""The one tool that writes to the Analyst's memory."""

from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.agent.envelope import Source, ToolResult, empty
from lotscope.agent.memory_service import remember
from lotscope.agent.tools.registry import ToolContext, tool

# The model is offered exactly the kinds the table accepts; test_memory keeps them in step.
MemoryKind = Literal["fact", "preference", "decision"]


class RememberInput(BaseModel):
    text: str = Field(
        min_length=3,
        max_length=500,
        description=(
            "The thing to remember, in the buyer's own words where you can. One fact per "
            "call: 'only buys west of Broad', not a paragraph."
        ),
    )
    kind: MemoryKind = Field(
        default="fact",
        description=(
            "preference for a rule they hold about what they buy, decision for a choice "
            "they made and its reason, fact for anything else durable about them."
        ),
    )


@tool(
    name="remember",
    description=(
        "Store something durable this buyer told you about themselves, so it survives into "
        "later conversations: where they will and will not buy, what they lost at auction, "
        "a rule they hold, a decision and its reason. Call it once, as they said it. Never "
        "use it for anything a tool returns — an owner, a price, a violation count, a sale "
        "status. Those change, and a remembered copy becomes a stale fact you will later "
        "assert as current."
    ),
    input_model=RememberInput,
)
async def remember_tool(
    session: AsyncSession, context: ToolContext, payload: RememberInput
) -> ToolResult:
    memory = await remember(
        session,
        context.user_id,
        kind=payload.kind,
        text=payload.text,
        source_run_id=context.agent_run_id,
    )
    if memory is None:
        return empty("That is already remembered word for word; nothing was stored again.")

    return ToolResult(
        data={
            "memory_id": memory.id,
            "kind": memory.kind,
            "text": memory.text,
            "remembered_in_run": context.agent_run_id,
        },
        sources=[Source(name="lotscope_memory", computed_at=memory.created_at)],
        unverified=[
            "This is what the buyer said, not something LotScope verified. It is memory, "
            "not evidence."
        ],
    )
