from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from lotscope.core.config import Settings
from lotscope.core.errors import UpstreamError
from lotscope.core.logging import get_logger


@dataclass(frozen=True)
class SkipTraceContacts:
    phones: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)


class SkipTraceProvider(Protocol):
    name: str

    async def trace(
        self, *, owner: str | None, mailing_address: str | None
    ) -> SkipTraceContacts: ...


class NullSkipTraceProvider:
    name = "null"

    async def trace(self, *, owner: str | None, mailing_address: str | None) -> SkipTraceContacts:
        return SkipTraceContacts()


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            ordered.append(cleaned)
    return ordered


def parse_batchdata_contacts(payload: dict[str, Any]) -> SkipTraceContacts:
    persons = payload.get("results", {}).get("persons", [])
    if not isinstance(persons, list):
        return SkipTraceContacts()
    phones: list[str] = []
    emails: list[str] = []
    for person in persons:
        if not isinstance(person, dict):
            continue
        for phone in person.get("phoneNumbers", []) or []:
            number = phone.get("number") if isinstance(phone, dict) else phone
            if isinstance(number, str):
                phones.append(number)
        for email in person.get("emails", []) or []:
            address = email.get("email") if isinstance(email, dict) else email
            if isinstance(address, str):
                emails.append(address)
    return SkipTraceContacts(phones=_dedupe(phones), emails=_dedupe(emails))


class BatchDataSkipTraceProvider:
    name = "batchdata"

    def __init__(self, *, api_key: str, api_url: str, timeout: float = 20.0) -> None:
        self._api_key = api_key
        self._api_url = api_url
        self._timeout = timeout
        self._logger = get_logger("skiptrace")

    async def trace(self, *, owner: str | None, mailing_address: str | None) -> SkipTraceContacts:
        request = {
            "requests": [{"name": {"full": owner or ""}, "propertyAddress": mailing_address or ""}]
        }
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(self._api_url, json=request, headers=headers)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as error:
            self._logger.warning("skiptrace_provider_error", error=str(error))
            raise UpstreamError("The skip-trace provider is unavailable.") from error
        return parse_batchdata_contacts(data)


def get_skiptrace_provider(settings: Settings) -> SkipTraceProvider | None:
    if settings.skiptrace_provider == "null":
        return NullSkipTraceProvider()
    if settings.skiptrace_provider == "batchdata" and settings.skiptrace_api_key:
        return BatchDataSkipTraceProvider(
            api_key=settings.skiptrace_api_key, api_url=settings.skiptrace_api_url
        )
    return None
