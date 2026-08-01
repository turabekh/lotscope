from dataclasses import dataclass


@dataclass(frozen=True)
class WideAreaCompPolicy:
    market: str
    radius_ft: float
    years: int


PHILADELPHIA_WIDE_AREA_V1 = WideAreaCompPolicy(market="phl", radius_ft=3000.0, years=5)

_REGISTRY: dict[str, WideAreaCompPolicy] = {
    PHILADELPHIA_WIDE_AREA_V1.market: PHILADELPHIA_WIDE_AREA_V1,
}


def wide_area_policy_for_market(market: str | None) -> WideAreaCompPolicy | None:
    if market is None:
        return None
    return _REGISTRY.get(market)
