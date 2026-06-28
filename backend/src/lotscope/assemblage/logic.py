from dataclasses import dataclass
from typing import Literal

Acquirability = Literal["same_owner", "city_owned", "vacant", "built"]
Potential = Literal["high", "medium", "low", "none"]

_ACQUIRABLE: frozenset[Acquirability] = frozenset({"same_owner", "city_owned", "vacant"})
_ACQUIRABILITY_RANK: dict[Acquirability, int] = {
    "same_owner": 0,
    "city_owned": 1,
    "vacant": 2,
    "built": 3,
}


@dataclass(frozen=True)
class TargetLot:
    lot_area_sqft: float | None
    frontage_ft: float | None


@dataclass(frozen=True)
class NeighborSignal:
    parcel_number: str
    same_owner: bool
    same_zoning: bool
    is_vacant: bool
    is_city_owned: bool
    lot_area_sqft: float | None
    frontage_ft: float | None


@dataclass(frozen=True)
class AssemblageSummary:
    adjacent_count: int
    candidate_count: int
    combined_lot_area_sqft: float | None
    combined_frontage_ft: float | None
    has_same_owner_neighbor: bool
    has_city_owned_neighbor: bool
    has_vacant_neighbor: bool


def classify_acquirability(signal: NeighborSignal) -> Acquirability:
    if signal.same_owner:
        return "same_owner"
    if signal.is_city_owned:
        return "city_owned"
    if signal.is_vacant:
        return "vacant"
    return "built"


def acquirability_rank(value: Acquirability) -> int:
    return _ACQUIRABILITY_RANK[value]


def is_candidate(signal: NeighborSignal) -> bool:
    return signal.same_zoning and classify_acquirability(signal) in _ACQUIRABLE


def summarize(target: TargetLot, neighbors: list[NeighborSignal]) -> AssemblageSummary:
    candidates = [n for n in neighbors if is_candidate(n)]
    combined_area: float | None = None
    combined_frontage: float | None = None
    if target.lot_area_sqft is not None:
        combined_area = round(
            target.lot_area_sqft + sum(n.lot_area_sqft or 0.0 for n in candidates), 1
        )
    if target.frontage_ft is not None:
        combined_frontage = round(
            target.frontage_ft + sum(n.frontage_ft or 0.0 for n in candidates), 1
        )
    return AssemblageSummary(
        adjacent_count=len(neighbors),
        candidate_count=len(candidates),
        combined_lot_area_sqft=combined_area,
        combined_frontage_ft=combined_frontage,
        has_same_owner_neighbor=any(n.same_owner for n in neighbors),
        has_city_owned_neighbor=any(n.is_city_owned for n in neighbors),
        has_vacant_neighbor=any(n.is_vacant for n in neighbors),
    )


def assess_potential(neighbors: list[NeighborSignal]) -> Potential:
    candidates = [n for n in neighbors if is_candidate(n)]
    if not candidates:
        return "none"
    has_clear_path = any(n.same_owner or n.is_city_owned for n in candidates)
    if has_clear_path or len(candidates) >= 2:
        return "high"
    return "medium"


def build_reasons(target: TargetLot, neighbors: list[NeighborSignal]) -> list[str]:
    candidates = [n for n in neighbors if is_candidate(n)]
    if not neighbors:
        return ["No adjacent parcels were found for this lot."]
    if not candidates:
        return [
            "Adjacent lots exist but none are an easy assemblage "
            "(same zoning and vacant, city-owned, or same owner)."
        ]
    reasons: list[str] = []
    same_owner = [n for n in candidates if n.same_owner]
    city_owned = [n for n in candidates if n.is_city_owned and not n.same_owner]
    vacant = [n for n in candidates if n.is_vacant and not n.same_owner and not n.is_city_owned]
    if same_owner:
        reasons.append(
            f"{len(same_owner)} adjacent lot(s) share this owner — already assembled or a "
            "single-seller deal."
        )
    if city_owned:
        reasons.append(
            f"{len(city_owned)} adjacent lot(s) are city or Land Bank owned — acquirable through "
            "public disposition."
        )
    if vacant:
        reasons.append(
            f"{len(vacant)} adjacent vacant lot(s) could be acquired to widen the development."
        )
    if target.lot_area_sqft is not None:
        combined = target.lot_area_sqft + sum(n.lot_area_sqft or 0.0 for n in candidates)
        reasons.append(
            f"Assembling the candidates could yield roughly {combined:,.0f} sqft of contiguous "
            "land (confirm zoning by-right outcomes for the combined lot)."
        )
    return reasons
