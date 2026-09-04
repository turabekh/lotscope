from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Literal

Status = Literal["green", "amber", "red"]
CadenceKind = Literal["daily", "weekly", "monthly", "quarterly", "seasonal", "manual"]

_INTERVAL: dict[str, timedelta] = {
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
    "monthly": timedelta(days=31),
    "quarterly": timedelta(days=92),
}

_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

_FAILED_STATUSES = frozenset({"failed", "error"})


@dataclass(frozen=True)
class Cadence:
    kind: CadenceKind
    season_months: tuple[int, ...] = field(default_factory=tuple)
    note: str = ""


@dataclass(frozen=True)
class FreshnessInput:
    status: str | None
    last_success_at: datetime | None
    last_attempt_at: datetime | None
    data_vintage: date | None = None


@dataclass(frozen=True)
class FreshnessVerdict:
    status: Status
    reason: str
    vintage_reason: str | None = None


DEFAULT_CADENCE = Cadence("monthly")

CADENCE: dict[tuple[str, str], Cadence] = {
    ("phl", "opa_properties_public"): Cadence("daily"),
    ("phl", "pwd_parcels"): Cadence("daily"),
    ("phl", "rtt_summary"): Cadence("daily"),
    ("phl", "real_estate_tax_delinquencies"): Cadence("daily"),
    ("phl", "violations"): Cadence("daily"),
    ("phl", "permits"): Cadence("daily"),
    ("phl", "demolitions"): Cadence("daily"),
    ("phl", "appeals"): Cadence("daily"),
    ("phl", "sheriff_sale"): Cadence("monthly"),
    ("phl", "buyer_profile"): Cadence("daily"),
    ("phl", "vacant_indicators"): Cadence("monthly"),
    ("phl", "zoning_base_districts"): Cadence("monthly"),
    ("phl", "zoning_overlays"): Cadence("monthly"),
    ("phl", "zoning_rco"): Cadence("monthly"),
    ("phl", "neighborhoods"): Cadence("monthly"),
    ("phl", "streets"): Cadence("monthly"),
    ("phl", "historicdistricts_local"): Cadence("monthly"),
    ("phl", "fema_flood"): Cadence("quarterly"),
}


def cadence_for(market: str, dataset: str) -> Cadence:
    return CADENCE.get((market, dataset), DEFAULT_CADENCE)


def _window_label(season_months: tuple[int, ...]) -> str:
    names = [_MONTHS[m - 1] for m in sorted(season_months) if 1 <= m <= 12]
    if not names:
        return "its season"
    if len(names) == 1:
        return names[0]
    return f"{names[0]} to {names[-1]}"


def _loaded_in_current_season(
    last_success: datetime, now: datetime, months: tuple[int, ...]
) -> bool:
    return last_success.year == now.year and last_success.month in months


def _describe_age(age: timedelta) -> str:
    days = age.days
    if days <= 0:
        return "today"
    if days == 1:
        return "1 day ago"
    return f"{days} days ago"


_SEVERITY: dict[Status, int] = {"green": 0, "amber": 1, "red": 2}

VINTAGE_UNKNOWN = "Vintage unknown - the source does not report what period its data covers."


def _vintage_verdict(
    row: FreshnessInput, cadence: Cadence, now: datetime
) -> FreshnessVerdict | None:
    if row.data_vintage is None or cadence.kind not in _INTERVAL:
        return None
    age = now.date() - row.data_vintage
    covers = f"data as of {row.data_vintage.isoformat()}"
    interval = _INTERVAL[cadence.kind]
    if age > 2 * interval:
        return FreshnessVerdict(
            "red", f"Stale - {covers}, {_describe_age(age)} (expected {cadence.kind})."
        )
    if age > interval:
        return FreshnessVerdict(
            "amber", f"Overdue - {covers}, {_describe_age(age)} (expected {cadence.kind})."
        )
    return FreshnessVerdict("green", f"Fresh - {covers}.")


def _worse(fetch: FreshnessVerdict, vintage: FreshnessVerdict | None) -> FreshnessVerdict:
    if vintage is None:
        return fetch
    if _SEVERITY[vintage.status] > _SEVERITY[fetch.status]:
        return FreshnessVerdict(vintage.status, vintage.reason, vintage_reason=vintage.reason)
    return FreshnessVerdict(fetch.status, fetch.reason, vintage_reason=vintage.reason)


def evaluate_freshness(row: FreshnessInput, cadence: Cadence, now: datetime) -> FreshnessVerdict:
    return _worse(_evaluate_fetch(row, cadence, now), _vintage_verdict(row, cadence, now))


def _evaluate_fetch(row: FreshnessInput, cadence: Cadence, now: datetime) -> FreshnessVerdict:
    if cadence.kind == "manual":
        if row.last_success_at is None:
            return FreshnessVerdict("amber", "Manual source — not yet loaded.")
        return FreshnessVerdict(
            "green", f"Manual source — as of {row.last_success_at.date().isoformat()}."
        )

    if cadence.kind == "seasonal":
        window = _window_label(cadence.season_months)
        if now.month not in cadence.season_months:
            return FreshnessVerdict("green", f"Off-season — next expected in {window}.")
        if (row.status or "").lower() in _FAILED_STATUSES:
            return FreshnessVerdict("red", "In-season and the last run failed.")
        if row.last_success_at is not None and _loaded_in_current_season(
            row.last_success_at, now, cadence.season_months
        ):
            return FreshnessVerdict("green", f"Loaded for the {now.year} {window} season.")
        return FreshnessVerdict("amber", f"In season ({window}) — awaiting the {now.year} publish.")

    if (row.status or "").lower() in _FAILED_STATUSES:
        return FreshnessVerdict("red", "Last run failed.")
    if row.last_success_at is None:
        return FreshnessVerdict("red", "No successful load on record.")

    interval = _INTERVAL[cadence.kind]
    age = now - row.last_success_at
    if age > 2 * interval:
        return FreshnessVerdict(
            "red", f"Stale — last success {_describe_age(age)} (expected {cadence.kind})."
        )
    if age > interval:
        return FreshnessVerdict(
            "amber", f"Overdue — last success {_describe_age(age)} (expected {cadence.kind})."
        )
    return FreshnessVerdict("green", f"Fresh — last success {_describe_age(age)}.")
