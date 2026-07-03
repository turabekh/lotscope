from dataclasses import dataclass
from typing import Any

CODE_SHERIFF_SALE = "sheriff_sale"
CODE_DELINQUENT = "delinquent"
CODE_TAX_UP = "tax_up"
CODE_LI_NEW = "li_new"
CODE_DANGER = "danger"
CODE_NEW_PERMIT = "new_permit"
CODE_NEW_DEMO = "new_demo"

SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"

EVENT_LABELS: dict[str, str] = {
    CODE_SHERIFF_SALE: "Sheriff sale",
    CODE_DELINQUENT: "New delinquency",
    CODE_TAX_UP: "Tax balance rose",
    CODE_LI_NEW: "New L&I violation",
    CODE_DANGER: "Dangerous / unsafe",
    CODE_NEW_PERMIT: "New permit",
    CODE_NEW_DEMO: "New demolition",
}


def event_label(code: str) -> str:
    return EVENT_LABELS.get(code, code)


@dataclass(frozen=True)
class TaxSnapshot:
    is_delinquent: bool | None
    total_due: float | None
    in_sheriff_sale: bool | None


@dataclass(frozen=True)
class EventDraft:
    code: str
    severity: str
    old_value: dict[str, Any] | None
    new_value: dict[str, Any] | None


def _became_true(old: bool | None, new: bool | None) -> bool:
    return bool(new) and not bool(old)


def classify_li_event(
    event_type: str, is_unsafe: bool | None, is_imminently_dangerous: bool | None
) -> EventDraft | None:
    if event_type == "violation":
        if is_unsafe or is_imminently_dangerous:
            return EventDraft(CODE_DANGER, SEVERITY_HIGH, None, {"event_type": event_type})
        return EventDraft(CODE_LI_NEW, SEVERITY_MEDIUM, None, {"event_type": event_type})
    if event_type == "permit":
        return EventDraft(CODE_NEW_PERMIT, SEVERITY_LOW, None, {"event_type": event_type})
    if event_type == "demolition":
        return EventDraft(CODE_NEW_DEMO, SEVERITY_HIGH, None, {"event_type": event_type})
    return None


def diff_tax(old: TaxSnapshot | None, new: TaxSnapshot) -> list[EventDraft]:
    if old is None:
        return []
    drafts: list[EventDraft] = []
    if _became_true(old.in_sheriff_sale, new.in_sheriff_sale):
        drafts.append(
            EventDraft(
                CODE_SHERIFF_SALE,
                SEVERITY_HIGH,
                {"in_sheriff_sale": old.in_sheriff_sale},
                {"in_sheriff_sale": new.in_sheriff_sale},
            )
        )
    if _became_true(old.is_delinquent, new.is_delinquent):
        drafts.append(
            EventDraft(
                CODE_DELINQUENT,
                SEVERITY_HIGH,
                {"is_delinquent": old.is_delinquent},
                {"is_delinquent": new.is_delinquent},
            )
        )
    if old.total_due is not None and new.total_due is not None and new.total_due > old.total_due:
        drafts.append(
            EventDraft(
                CODE_TAX_UP,
                SEVERITY_MEDIUM,
                {"total_due": old.total_due},
                {"total_due": new.total_due},
            )
        )
    return drafts
