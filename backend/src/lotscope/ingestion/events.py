from dataclasses import dataclass
from typing import Any

CODE_SHERIFF_SALE = "sheriff_sale"
CODE_DELINQUENT = "delinquent"
CODE_TAX_UP = "tax_up"

SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"


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
