from collections.abc import AsyncIterator
from typing import Any

from anthropic import AsyncAnthropic

from lotscope.core.config import Settings


class AnthropicToolClient:
    def __init__(self, settings: Settings) -> None:
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is not configured.")
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def stream(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int,
    ) -> AsyncIterator[dict[str, Any]]:
        async with self._client.messages.stream(
            model=model,
            system=system,
            messages=messages,  # type: ignore[arg-type]
            tools=tools,  # type: ignore[arg-type]
            max_tokens=max_tokens,
        ) as stream:
            async for event in stream:
                if event.type == "text" and event.text:
                    yield {"type": "text_delta", "text": event.text}
            final = await stream.get_final_message()
            yield {
                "type": "message",
                "content": [block.model_dump() for block in final.content],
                "stop_reason": final.stop_reason,
                "usage": {
                    "input_tokens": final.usage.input_tokens,
                    "output_tokens": final.usage.output_tokens,
                },
            }
