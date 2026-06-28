from dataclasses import dataclass
from typing import Any, Literal

Severity = Literal["high", "medium", "info"]


@dataclass(frozen=True)
class Change:
    code: str
    label: str
    severity: Severity


def _num(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def compute_changes(snapshot: dict[str, Any] | None, current: dict[str, Any]) -> list[Change]:
    if not snapshot:
        return []
    changes: list[Change] = []

    if current.get("in_sheriff_sale") and not snapshot.get("in_sheriff_sale"):
        changes.append(Change("sheriff_sale", "Now flagged for sheriff sale", "high"))

    if current.get("is_delinquent") and not snapshot.get("is_delinquent"):
        changes.append(Change("delinquent", "Became tax-delinquent", "high"))

    cur_due = _num(current.get("total_due")) or 0.0
    snap_due = _num(snapshot.get("total_due")) or 0.0
    if cur_due - snap_due > 0.5:
        changes.append(Change("tax_up", f"Tax owed +${cur_due - snap_due:,.0f}", "medium"))

    cur_v = int(current.get("violations") or 0)
    snap_v = int(snapshot.get("violations") or 0)
    if cur_v > snap_v:
        changes.append(Change("li_new", f"{cur_v - snap_v} new L&I violation(s)", "medium"))

    if current.get("dangerous") and not snapshot.get("dangerous"):
        changes.append(Change("danger", "New unsafe / dangerous L&I flag", "high"))

    if bool(current.get("is_vacant")) != bool(snapshot.get("is_vacant")):
        label = "Now flagged vacant" if current.get("is_vacant") else "No longer flagged vacant"
        changes.append(Change("vacancy", label, "info"))

    cur_mv = _num(current.get("market_value"))
    snap_mv = _num(snapshot.get("market_value"))
    if cur_mv is not None and snap_mv is not None and abs(cur_mv - snap_mv) > 0.5:
        delta = cur_mv - snap_mv
        sign = "+" if delta > 0 else "-"
        changes.append(Change("assessment", f"Assessment {sign}${abs(delta):,.0f}", "info"))

    cur_op = current.get("opportunity_score")
    snap_op = snapshot.get("opportunity_score")
    if cur_op is not None and snap_op is not None and cur_op != snap_op:
        changes.append(Change("opportunity", f"Opportunity {snap_op} → {cur_op}", "info"))

    cur_d = current.get("distress_score")
    snap_d = snapshot.get("distress_score")
    if cur_d is not None and snap_d is not None and cur_d > snap_d:
        changes.append(Change("distress", f"Distress {snap_d} → {cur_d}", "medium"))

    return changes
