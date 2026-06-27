from typing import Any, Protocol, cast

from anthropic import AsyncAnthropic
from anthropic.types import (
    MessageParam,
    ToolChoiceToolParam,
    ToolParam,
    ToolUseBlock,
)
from pydantic import BaseModel

from lotscope.ai.errors import GenerationError
from lotscope.core.config import Settings

_TOOL_NAME = "structured_answer"


class StructuredGenerator(Protocol):
    async def generate(
        self, *, system: str, user: str, schema: type[BaseModel]
    ) -> dict[str, Any]: ...


class AnthropicGenerator:
    def __init__(self, settings: Settings, *, max_tokens: int = 1024) -> None:
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._model = settings.anthropic_model
        self._max_tokens = max_tokens

    async def generate(self, *, system: str, user: str, schema: type[BaseModel]) -> dict[str, Any]:
        tool = cast(
            ToolParam,
            {
                "name": _TOOL_NAME,
                "description": "Return the answer strictly in this structure.",
                "input_schema": schema.model_json_schema(),
            },
        )
        tool_choice = cast(ToolChoiceToolParam, {"type": "tool", "name": _TOOL_NAME})
        messages = [cast(MessageParam, {"role": "user", "content": user})]
        message = await self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            tools=[tool],
            tool_choice=tool_choice,
            messages=messages,
        )
        for block in message.content:
            if isinstance(block, ToolUseBlock) and block.name == _TOOL_NAME:
                return cast(dict[str, Any], block.input)
        raise GenerationError("The model did not return a structured answer.")
