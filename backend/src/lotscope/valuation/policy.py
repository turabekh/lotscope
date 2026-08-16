from dataclasses import dataclass


@dataclass(frozen=True)
class CompSelectionPolicy:
    market: str
    version: str
    excluded_document_types: frozenset[str]
    lot_area_ratio_min: float
    lot_area_ratio_max: float
    min_similar_comps: int


PHILADELPHIA_COMP_SELECTION_V1 = CompSelectionPolicy(
    market="phl",
    version="phl-comp-selection-v1",
    excluded_document_types=frozenset(
        {
            "SHERIFF'S DEED",
            "DEED LAND BANK",
            "DEED - DECEASED",
            "DEED OF CONDEMNATION",
            "MISCELLANEOUS DEED",
        }
    ),
    lot_area_ratio_min=0.6,
    lot_area_ratio_max=1.6,
    min_similar_comps=3,
)

_REGISTRY: dict[str, CompSelectionPolicy] = {
    PHILADELPHIA_COMP_SELECTION_V1.market: PHILADELPHIA_COMP_SELECTION_V1,
}


def comp_selection_policy_for_market(market: str | None) -> CompSelectionPolicy | None:
    if market is None:
        return None
    return _REGISTRY.get(market)


def excluded_document_types_for_market(market: str | None) -> list[str] | None:
    policy = comp_selection_policy_for_market(market)
    if policy is None or not policy.excluded_document_types:
        return None
    return sorted(policy.excluded_document_types)
