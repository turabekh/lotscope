from collections.abc import Iterable
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

Tier = Literal["high", "medium", "low", "none"]


class DistressFactor(BaseModel):
    code: str
    label: str
    weight: int


class DistressResult(BaseModel):
    parcel_number: str
    score: int
    tier: Tier
    version: str
    profile_id: str
    factors: list[DistressFactor]
    sources: list[dict[str, Any]]
    computed_at: datetime


class LeadItem(BaseModel):
    parcel_number: str
    address: str | None
    owner: str | None
    base_zoning_code: str | None
    is_vacant: bool | None
    market_value: float | None
    total_due: float | None
    in_sheriff_sale: bool | None
    score: int
    top_factors: list[str]
    deal_score: float | None = None
    max_allowable_offer: float | None = None
    is_underpriced: bool | None = None


class LeadsResponse(BaseModel):
    limit: int
    returned: int
    leads: list[LeadItem]


class MailRecipient(BaseModel):
    parcel_number: str
    property_address: str | None
    owner: str
    mailing_address: str


def build_mail_recipients(
    rows: Iterable[Any], *, one_per_owner: bool = False
) -> list[MailRecipient]:
    recipients: list[MailRecipient] = []
    seen_owners: set[tuple[str, str]] = set()
    for row in rows:
        owner = (row.owner or "").strip()
        mailing_address = (row.mailing_address or "").strip()
        if not owner or not mailing_address:
            continue
        if one_per_owner:
            key = (owner.casefold(), mailing_address.casefold())
            if key in seen_owners:
                continue
            seen_owners.add(key)
        recipients.append(
            MailRecipient(
                parcel_number=row.parcel_number,
                property_address=row.address,
                owner=owner,
                mailing_address=mailing_address,
            )
        )
    return recipients
