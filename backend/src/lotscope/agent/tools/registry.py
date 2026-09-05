from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.agent.envelope import ToolResult

TInput = TypeVar("TInput", bound=BaseModel)

ToolHandler = Callable[[AsyncSession, "ToolContext", Any], Awaitable[ToolResult]]


@dataclass(frozen=True)
class ToolContext:
    user_id: int
    buy_box: dict[str, Any] = field(default_factory=dict)
    owned_parcels: tuple[str, ...] = ()
    agent_run_id: int | None = None


@dataclass(frozen=True)
class RegisteredTool:
    name: str
    description: str
    input_model: type[BaseModel]
    handler: ToolHandler
    long_running: bool = False

    def schema(self) -> dict[str, Any]:
        raw = self.input_model.model_json_schema()
        raw.pop("title", None)
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": raw,
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, tool: RegisteredTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"A tool named {tool.name!r} is already registered.")
        self._tools[tool.name] = tool

    def get(self, name: str) -> RegisteredTool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def schemas(self) -> list[dict[str, Any]]:
        return [self._tools[name].schema() for name in self.names()]

    def clear(self) -> None:
        self._tools.clear()


REGISTRY = ToolRegistry()


def tool(
    *,
    name: str,
    description: str,
    input_model: type[BaseModel],
    long_running: bool = False,
    registry: ToolRegistry | None = None,
) -> Callable[[ToolHandler], ToolHandler]:
    def decorate(handler: ToolHandler) -> ToolHandler:
        (registry or REGISTRY).register(
            RegisteredTool(
                name=name,
                description=description,
                input_model=input_model,
                handler=handler,
                long_running=long_running,
            )
        )
        return handler

    return decorate
