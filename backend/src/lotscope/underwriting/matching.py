from dataclasses import dataclass
from typing import Any, Literal

from lotscope.buybox.schemas import BuyBoxRead
from lotscope.core.config import get_settings

MATCH_VERSION = "m2"

SFHA_ZONE_PREDICATE = (
    "(upper(f.zone) LIKE 'A%' OR upper(f.zone) LIKE 'V%' "
    "OR upper(f.zone) LIKE '%100 YEAR%' OR upper(f.zone) LIKE '%1%% ANNUAL%' "
    "OR upper(f.zone) LIKE '%1 PCT ANNUAL%')"
)

CriterionStatus = Literal["met", "not_met", "not_evaluated"]

_UNKNOWN_OFFER = "No maximum allowable offer could be calculated, so affordability is unconfirmed."
_UNKNOWN_MARGIN = "No estimated margin is available, so the return target is unconfirmed."
_UNKNOWN_LOT_AREA = "No lot area is recorded, so the size floor is unconfirmed."
_UNKNOWN_ZONING = "No base zoning district is recorded, so the district filter is unconfirmed."


@dataclass(frozen=True)
class MatchCandidate:
    parcel_number: str
    max_allowable_offer: float | None
    est_margin: float | None
    lot_area_sqft: float | None = None
    base_zoning_code: str | None = None


@dataclass(frozen=True)
class CriterionOutcome:
    name: str
    status: CriterionStatus
    detail: str


@dataclass(frozen=True)
class MatchResult:
    matched: bool
    criteria: list[CriterionOutcome]


def required_margin(buy_box: BuyBoxRead) -> float:
    return buy_box.assumptions.get("target_margin", get_settings().deal_target_margin)


def _price_outcome(candidate: MatchCandidate, ceiling: float) -> CriterionOutcome:
    if candidate.max_allowable_offer is None:
        return CriterionOutcome("max_bid", "not_evaluated", _UNKNOWN_OFFER)
    if candidate.max_allowable_offer <= ceiling:
        return CriterionOutcome(
            "max_bid",
            "met",
            f"Maximum allowable offer ${candidate.max_allowable_offer:,.0f} "
            f"is within your ${ceiling:,.0f} ceiling.",
        )
    return CriterionOutcome(
        "max_bid",
        "not_met",
        f"Maximum allowable offer ${candidate.max_allowable_offer:,.0f} "
        f"exceeds your ${ceiling:,.0f} ceiling.",
    )


def _margin_outcome(candidate: MatchCandidate, target: float) -> CriterionOutcome:
    if candidate.est_margin is None:
        return CriterionOutcome("target_margin", "not_evaluated", _UNKNOWN_MARGIN)
    if candidate.est_margin >= target:
        return CriterionOutcome(
            "target_margin",
            "met",
            f"Estimated margin {candidate.est_margin:.1%} meets your {target:.1%} target.",
        )
    return CriterionOutcome(
        "target_margin",
        "not_met",
        f"Estimated margin {candidate.est_margin:.1%} is below your {target:.1%} target.",
    )


def _lot_area_outcome(candidate: MatchCandidate, minimum: int) -> CriterionOutcome:
    if candidate.lot_area_sqft is None:
        return CriterionOutcome("min_lot_sqft", "not_evaluated", _UNKNOWN_LOT_AREA)
    if candidate.lot_area_sqft >= minimum:
        return CriterionOutcome(
            "min_lot_sqft",
            "met",
            f"{candidate.lot_area_sqft:,.0f} sqft meets your {minimum:,} sqft floor.",
        )
    return CriterionOutcome(
        "min_lot_sqft",
        "not_met",
        f"{candidate.lot_area_sqft:,.0f} sqft is below your {minimum:,} sqft floor.",
    )


def _zoning_outcome(candidate: MatchCandidate, codes: list[str]) -> CriterionOutcome:
    if candidate.base_zoning_code is None:
        return CriterionOutcome("zoning_codes", "not_evaluated", _UNKNOWN_ZONING)
    if candidate.base_zoning_code.upper() in {code.upper() for code in codes}:
        return CriterionOutcome(
            "zoning_codes", "met", f"{candidate.base_zoning_code} is one of your districts."
        )
    return CriterionOutcome(
        "zoning_codes",
        "not_met",
        f"{candidate.base_zoning_code} is not one of your districts.",
    )


def evaluate_buy_box(candidate: MatchCandidate, buy_box: BuyBoxRead) -> MatchResult:
    criteria: list[CriterionOutcome] = []
    if buy_box.max_bid is not None:
        criteria.append(_price_outcome(candidate, buy_box.max_bid))
    criteria.append(_margin_outcome(candidate, required_margin(buy_box)))
    if buy_box.min_lot_sqft is not None:
        criteria.append(_lot_area_outcome(candidate, buy_box.min_lot_sqft))
    if buy_box.zoning_codes:
        criteria.append(_zoning_outcome(candidate, buy_box.zoning_codes))
    return MatchResult(
        matched=all(outcome.status == "met" for outcome in criteria),
        criteria=criteria,
    )


def match_conditions(buy_box: BuyBoxRead) -> tuple[list[str], dict[str, Any]]:
    conditions: list[str] = []
    params: dict[str, Any] = {}
    if buy_box.max_bid is not None:
        conditions.append("v.max_allowable_offer <= :max_bid")
        params["max_bid"] = buy_box.max_bid
    conditions.append("v.est_margin >= :target_margin")
    params["target_margin"] = required_margin(buy_box)
    if buy_box.min_lot_sqft is not None:
        conditions.append("p.lot_area_sqft >= :min_lot_sqft")
        params["min_lot_sqft"] = buy_box.min_lot_sqft
    if buy_box.zoning_codes:
        conditions.append("upper(p.base_zoning_code) = ANY(:zoning_codes)")
        params["zoning_codes"] = [code.upper() for code in buy_box.zoning_codes]
    if buy_box.exclude_historic:
        conditions.append(
            "NOT EXISTS (SELECT 1 FROM historic_district h "
            "WHERE ST_Intersects(h.geom_local, p.geom_local))"
        )
    if buy_box.exclude_flood:
        conditions.append(
            "NOT EXISTS (SELECT 1 FROM flood_zone f "
            "WHERE ST_Intersects(f.geom_local, p.geom_local) AND " + SFHA_ZONE_PREDICATE + ")"
        )
    return conditions, params
