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

COMP_SELECTION = PHILADELPHIA_COMP_SELECTION_V1


def excluded_document_types() -> list[str]:
    return sorted(COMP_SELECTION.excluded_document_types)
