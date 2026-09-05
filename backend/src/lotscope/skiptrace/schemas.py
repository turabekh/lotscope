from pydantic import BaseModel


class SkipTraceContactsOut(BaseModel):
    phones: list[str]
    emails: list[str]


class SkipTraceResultOut(BaseModel):
    parcel_number: str
    owner: str | None
    contacts: SkipTraceContactsOut
    cached: bool


class CreditCheckoutRequest(BaseModel):
    pack: str
