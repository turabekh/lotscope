from datetime import date
from typing import Any


def first_present(values: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if values.get(key) not in (None, ""):
            return values[key]
    return None


def parse_iso_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None
