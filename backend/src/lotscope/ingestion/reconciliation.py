import re
from collections.abc import Iterable
from dataclasses import dataclass, field

_NON_DIGIT = re.compile(r"\D")
_OPA_ACCOUNT_LENGTH = 9
_MARKET_KEY_SEP = ":"
_DEFAULT_MARKET = "phl"


def normalize_account(raw: str | int | None) -> str | None:
    if raw is None:
        return None
    digits = _NON_DIGIT.sub("", str(raw).strip())
    if not digits or len(digits) > _OPA_ACCOUNT_LENGTH:
        return None
    return digits.zfill(_OPA_ACCOUNT_LENGTH)


def to_parcel_key(raw: str | int | None, *, market: str = _DEFAULT_MARKET) -> str | None:
    local = normalize_account(raw)
    return f"{market}{_MARKET_KEY_SEP}{local}" if local is not None else None


def normalize_pwd_id(raw: str | int | None) -> str | None:
    if raw is None:
        return None
    cleaned = str(raw).strip().upper()
    return cleaned or None


@dataclass(frozen=True)
class SourceRecord:
    source: str
    opa_account: str | int | None = None
    brt_number: str | int | None = None
    pwd_parcel_id: str | int | None = None


@dataclass
class ReconciledParcel:
    parcel_number: str
    pwd_parcel_id: str | None = None
    brt_number: str | None = None
    sources: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReconciliationResult:
    parcels: list[ReconciledParcel]
    unresolved: list[SourceRecord]


def canonical_parcel_number(record: SourceRecord) -> str | None:
    local = normalize_account(record.opa_account) or normalize_account(record.brt_number)
    return f"{_DEFAULT_MARKET}{_MARKET_KEY_SEP}{local}" if local is not None else None


def reconcile(records: Iterable[SourceRecord]) -> ReconciliationResult:
    grouped: dict[str, ReconciledParcel] = {}
    unresolved: list[SourceRecord] = []
    for record in records:
        key = canonical_parcel_number(record)
        if key is None:
            unresolved.append(record)
            continue
        parcel = grouped.get(key)
        if parcel is None:
            parcel = ReconciledParcel(parcel_number=key)
            grouped[key] = parcel
        if parcel.pwd_parcel_id is None:
            parcel.pwd_parcel_id = normalize_pwd_id(record.pwd_parcel_id)
        if parcel.brt_number is None:
            parcel.brt_number = normalize_account(record.brt_number)
        if record.source not in parcel.sources:
            parcel.sources.append(record.source)
    for parcel in grouped.values():
        parcel.sources.sort()
    parcels = sorted(grouped.values(), key=lambda parcel: parcel.parcel_number)
    return ReconciliationResult(parcels=parcels, unresolved=unresolved)
