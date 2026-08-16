from collections.abc import Iterable
from datetime import date


def vintage_from_year_month(values: Iterable[str | None]) -> date | None:
    periods = sorted(
        value.strip()
        for value in values
        if value is not None and len(value.strip()) == 6 and value.strip().isdigit()
    )
    if not periods:
        return None
    latest = periods[-1]
    year, month = int(latest[:4]), int(latest[4:])
    if not 1 <= month <= 12:
        return None
    return date(year, month, 1)


def vintage_from_dates(values: Iterable[date | None]) -> date | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    today = date.today()
    dated = [value for value in present if value <= today]
    return max(dated) if dated else None
