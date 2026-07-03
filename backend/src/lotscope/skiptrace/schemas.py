from datetime import datetime

from pydantic import BaseModel


class SkipTraceContactsOut(BaseModel):
    phones: list[str]
    emails: list[str]


class SkipTraceResultOut(BaseModel):
    parcel_number: str
    owner: str | None
    contacts: SkipTraceContactsOut
    credits_spent: int
    credits_remaining: int
    cached: bool


class CreditLedgerItem(BaseModel):
    delta: int
    reason: str
    ref: str | None
    created_at: datetime


class CreditBalance(BaseModel):
    balance: int
    entries: list[CreditLedgerItem]


class CreditCheckoutRequest(BaseModel):
    pack: str


class CreditCheckoutResponse(BaseModel):
    url: str
