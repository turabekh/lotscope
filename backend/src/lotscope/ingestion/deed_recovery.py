from collections import Counter
from dataclasses import dataclass

from lotscope.ingestion.street_address import normalize_street_address


@dataclass(frozen=True)
class RecoveryOutcome:
    parcel_number: str | None
    reason: str


UNRESOLVED_NO_ADDRESS = "no street address on the deed"
UNRESOLVED_NO_MATCH = "no parcel matches the deed address"
UNRESOLVED_COLLISION = "more than one parcel matches the deed address"
RESOLVED = "matched a single parcel by address"


def build_address_index(rows: list[tuple[str, str | None]]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for parcel_number, address in rows:
        key = normalize_street_address(address)
        if key is None:
            continue
        index.setdefault(key, []).append(parcel_number)
    return index


def recover_parcel(street_address: str | None, index: dict[str, list[str]]) -> RecoveryOutcome:
    key = normalize_street_address(street_address)
    if key is None:
        return RecoveryOutcome(None, UNRESOLVED_NO_ADDRESS)
    matches = index.get(key, [])
    if not matches:
        return RecoveryOutcome(None, UNRESOLVED_NO_MATCH)
    if len(set(matches)) > 1:
        return RecoveryOutcome(None, UNRESOLVED_COLLISION)
    return RecoveryOutcome(matches[0], RESOLVED)


def summarise(outcomes: list[RecoveryOutcome]) -> Counter[str]:
    return Counter(outcome.reason for outcome in outcomes)
