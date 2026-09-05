from typing import Any

from anthropic import AsyncAnthropic

from lotscope.core.config import Settings


class AnthropicToolClient:
    def __init__(self, settings: Settings) -> None:
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is not configured.")
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def complete(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int,
    ) -> dict[str, Any]:
        response = await self._client.messages.create(
            model=model,
            system=system,
            messages=messages,  # type: ignore[arg-type]
            tools=tools,  # type: ignore[arg-type]
            max_tokens=max_tokens,
        )
        return {
            "content": [block.model_dump() for block in response.content],
            "stop_reason": response.stop_reason,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        }
