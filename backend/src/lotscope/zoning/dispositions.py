from typing import Any, Literal

FieldDisposition = Literal["unregulated", "conditional"]

DISPOSITION_FIELDS = (
    "min_lot_area_sqft",
    "min_lot_width_ft",
    "max_height_ft",
    "max_units",
    "max_occupancy_pct",
    "max_floor_area_ratio_pct",
)


def disposition_of(
    dispositions: dict[str, Any] | None, field: str
) -> tuple[FieldDisposition | None, str | None]:
    entry = (dispositions or {}).get(field)
    if not isinstance(entry, dict):
        return None, None
    disposition = entry.get("disposition")
    if disposition not in ("unregulated", "conditional"):
        return None, None
    note = entry.get("note")
    return disposition, note if isinstance(note, str) else None


def is_unregulated(dispositions: dict[str, Any] | None, field: str) -> bool:
    return disposition_of(dispositions, field)[0] == "unregulated"


def is_evaluable(dispositions: dict[str, Any] | None, field: str, value: float | None) -> bool:
    if value is not None:
        return True
    return is_unregulated(dispositions, field)
