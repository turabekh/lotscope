import asyncio
import json
from dataclasses import dataclass
from typing import Any, Protocol

from py_vapid import Vapid01
from pywebpush import WebPushException, webpush

from lotscope.core.config import Settings


@dataclass(frozen=True)
class PushSubscriptionInfo:
    endpoint: str
    p256dh: str
    auth: str


class PushExpiredError(Exception):
    pass


class PushSender(Protocol):
    async def send(
        self, subscription: PushSubscriptionInfo, *, title: str, body: str, url: str
    ) -> None: ...


class WebPushSender:
    def __init__(self, settings: Settings) -> None:
        if not settings.vapid_private_key:
            raise ValueError("Web push is not configured.")
        self._vapid = Vapid01.from_raw(settings.vapid_private_key.encode())
        self._subject = settings.vapid_subject

    async def send(
        self, subscription: PushSubscriptionInfo, *, title: str, body: str, url: str
    ) -> None:
        info: dict[str, Any] = {
            "endpoint": subscription.endpoint,
            "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
        }
        payload = json.dumps({"title": title, "body": body, "url": url})
        await asyncio.to_thread(self._send_sync, info, payload)

    def _send_sync(self, info: dict[str, Any], payload: str) -> None:
        try:
            webpush(
                info,
                data=payload,
                vapid_private_key=self._vapid,
                vapid_claims={"sub": self._subject},
            )
        except WebPushException as error:
            status = getattr(error.response, "status_code", None)
            if status in (404, 410):
                raise PushExpiredError from error
            raise


def get_push_sender(settings: Settings) -> PushSender | None:
    if not settings.vapid_private_key:
        return None
    return WebPushSender(settings)
