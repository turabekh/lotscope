from dataclasses import dataclass, field
from typing import Protocol

from lotscope.core.config import Settings


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


def get_skiptrace_provider(settings: Settings) -> SkipTraceProvider | None:
    if settings.skiptrace_provider == "null":
        return NullSkipTraceProvider()
    return None
