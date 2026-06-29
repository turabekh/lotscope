from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass(frozen=True)
class FetchedDeed:
    external_id: str
    parcel_number: str
    data: bytes
    document_type: str | None = None
    recording_date: date | None = None


class DeedSource(Protocol):
    async def fetch_for_parcel(self, parcel_number: str) -> list[FetchedDeed]: ...
