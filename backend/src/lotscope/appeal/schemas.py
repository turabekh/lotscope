from pydantic import BaseModel


class AppealPacketStatus(BaseModel):
    parcel_number: str
    entitled: bool
    source: str | None
    packet_credits: int
