import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from lotscope.agent.runtime import AgentEvent

RETRY_MS = 3000
_CANCELLED: set[int] = set()


def cancel_run(run_id: int) -> None:
    _CANCELLED.add(run_id)


def is_cancelled(run_id: int) -> bool:
    return run_id in _CANCELLED


def clear_cancellation(run_id: int) -> None:
    _CANCELLED.discard(run_id)


def format_event(event: AgentEvent) -> str:
    payload = json.dumps(event.payload, default=str)
    return f"event: {event.kind}\ndata: {payload}\n\n"


async def sse(events: AsyncIterator[AgentEvent]) -> AsyncIterator[str]:
    yield f"retry: {RETRY_MS}\n\n"
    async for event in events:
        yield format_event(event)


async def replay(steps: list[dict[str, Any]]) -> AsyncIterator[AgentEvent]:
    for step in steps:
        if step["kind"] == "text":
            yield AgentEvent("text", {"text": step.get("text") or ""})
        elif step["kind"] == "tool":
            envelope = step.get("envelope") or {}
            yield AgentEvent(
                "tool_started",
                {"tool": step.get("tool_name"), "input": step.get("tool_input") or {}},
            )
            yield AgentEvent(
                "tool_finished",
                {
                    "tool": step.get("tool_name"),
                    "sources": envelope.get("sources", []),
                    "unverified": envelope.get("unverified", []),
                    "duration_ms": step.get("duration_ms"),
                },
            )
        await asyncio.sleep(0)
