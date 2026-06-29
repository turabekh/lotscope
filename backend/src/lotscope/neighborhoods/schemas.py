from pydantic import BaseModel


class NeighborhoodSummary(BaseModel):
    name: str


class NeighborhoodListResponse(BaseModel):
    neighborhoods: list[NeighborhoodSummary]
