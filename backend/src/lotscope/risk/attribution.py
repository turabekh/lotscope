from dataclasses import dataclass
from datetime import date
from typing import Literal

from lotscope.risk.party_match import match_parties

RiskPosture = Literal["current_owner", "likely_discharged", "verify", "unknown_debtor"]

SHERIFF_DEED = "SHERIFF'S DEED"
NOMINAL_CONSIDERATION = 1.0


@dataclass(frozen=True)
class TransferAfterSnapshot:
    grantor: str | None
    document_type: str | None
    document_id: str | None
    sale_date: date | None
    sale_price: float | None

    @property
    def is_sheriff_deed(self) -> bool:
        return (self.document_type or "").strip().upper() == SHERIFF_DEED

    @property
    def is_nominal(self) -> bool:
        return self.sale_price is not None and self.sale_price <= NOMINAL_CONSIDERATION


@dataclass(frozen=True)
class DelinquencyAttribution:
    posture: RiskPosture
    counts_toward_distress: bool
    note: str


def _snapshot_label(snapshot_period: str | None) -> str:
    if snapshot_period is None or len(snapshot_period) != 6:
        return "the recorded snapshot"
    return f"{snapshot_period[:4]}-{snapshot_period[4:]}"


def _deed_label(transfer: TransferAfterSnapshot) -> str:
    when = transfer.sale_date.isoformat() if transfer.sale_date else "an undated"
    document = f" (doc {transfer.document_id})" if transfer.document_id else ""
    return f"{when} {(transfer.document_type or 'deed').lower()}{document}"


def attribute_delinquency(
    *,
    delinquency_owner: str | None,
    current_owner: str | None,
    snapshot_period: str | None,
    transfer: TransferAfterSnapshot | None,
) -> DelinquencyAttribution:
    vintage = _snapshot_label(snapshot_period)

    if delinquency_owner is None:
        return DelinquencyAttribution(
            posture="unknown_debtor",
            counts_toward_distress=True,
            note=(
                f"Recorded as of {vintage}; the source does not name who owes it, so it is "
                "reported against the parcel as recorded."
            ),
        )

    against_owner = match_parties(delinquency_owner, current_owner)

    if against_owner.strength == "exact":
        return DelinquencyAttribution(
            posture="current_owner",
            counts_toward_distress=True,
            note=f"Recorded as of {vintage} against the current owner.",
        )

    if against_owner.strength == "partial":
        return DelinquencyAttribution(
            posture="current_owner",
            counts_toward_distress=True,
            note=(
                f"Recorded as of {vintage} against {delinquency_owner}, which partly matches the "
                "current owner. Treated as the current owner's because the match is ambiguous."
            ),
        )

    if transfer is None:
        return DelinquencyAttribution(
            posture="verify",
            counts_toward_distress=False,
            note=(
                f"Recorded as of {vintage} against {delinquency_owner}, who is not the owner of "
                "record. No later transfer explains the difference — verify with the Dept. of "
                "Revenue."
            ),
        )

    if transfer.is_nominal:
        return DelinquencyAttribution(
            posture="verify",
            counts_toward_distress=True,
            note=(
                f"Recorded as of {vintage} against {delinquency_owner}. Title moved by "
                f"{_deed_label(transfer)} for nominal consideration, which can re-title a "
                "property without changing the household — the debt is still treated as the "
                "owner's."
            ),
        )

    grantor_match = match_parties(delinquency_owner, transfer.grantor)

    if transfer.is_sheriff_deed and grantor_match.strength in ("exact", "partial"):
        return DelinquencyAttribution(
            posture="likely_discharged",
            counts_toward_distress=False,
            note=(
                f"Recorded as of {vintage} against {delinquency_owner}, the prior owner named as "
                f"grantor on the {_deed_label(transfer)}. Debt predates the current owner and is "
                "likely discharged at sheriff sale — verify with the Dept. of Revenue."
            ),
        )

    return DelinquencyAttribution(
        posture="verify",
        counts_toward_distress=False,
        note=(
            f"Recorded as of {vintage} against {delinquency_owner}, not the owner of record. "
            f"Title moved by {_deed_label(transfer)}; an arm's-length sale normally clears "
            "delinquency at closing, but liens run with the land — verify with the Dept. of "
            "Revenue before relying on it."
        ),
    )
