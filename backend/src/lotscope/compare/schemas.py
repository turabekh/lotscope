from pydantic import BaseModel

from lotscope.parcels.schemas import ParcelDetail
from lotscope.verdict.schemas import VerdictResult


class ParcelCompareItem(BaseModel):
    detail: ParcelDetail
    verdict: VerdictResult | None


class ParcelCompareResponse(BaseModel):
    items: list[ParcelCompareItem]
