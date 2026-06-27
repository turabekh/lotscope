from pydantic import BaseModel


class ParcelSearchResult(BaseModel):
    parcel_number: str
    address: str | None
    owner: str | None
    score: float


class ParcelSearchResponse(BaseModel):
    query: str
    results: list[ParcelSearchResult]
