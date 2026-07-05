import asyncio
from collections.abc import Awaitable, Callable

import httpx

from lotscope.core.errors import LotScopeError

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


async def request_with_retry(
    send: Callable[[], Awaitable[httpx.Response]],
    *,
    max_retries: int,
    backoff: float,
    error: type[LotScopeError],
    retryable_status: frozenset[int] = RETRYABLE_STATUS,
) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            response = await send()
            response.raise_for_status()
        except httpx.HTTPStatusError as status_error:
            last_error = status_error
            if status_error.response.status_code not in retryable_status:
                raise error(
                    f"Upstream returned {status_error.response.status_code}"
                ) from status_error
        except httpx.HTTPError as transport_error:
            last_error = transport_error
        else:
            return response
        if attempt < max_retries:
            await asyncio.sleep(backoff * (2**attempt))
    raise error("Request failed after retries") from last_error
