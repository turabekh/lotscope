from dataclasses import dataclass


@dataclass(frozen=True)
class WideAreaCompPolicy:
    market: str
    radius_ft: float
    years: int


PHILADELPHIA_WIDE_AREA_V1 = WideAreaCompPolicy(market="phl", radius_ft=3000.0, years=5)

WIDE_AREA = PHILADELPHIA_WIDE_AREA_V1
