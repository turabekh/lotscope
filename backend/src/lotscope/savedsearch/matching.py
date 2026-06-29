from collections.abc import Iterable
from typing import Any

from lotscope.savedsearch.schemas import SearchCriteria

MATCH_BASE = (
    "FROM parcel p "
    "LEFT JOIN parcel_verdict pv ON pv.parcel_number = p.parcel_number "
    "LEFT JOIN parcel_distress pd ON pd.parcel_number = p.parcel_number "
    "LEFT JOIN tax_status ts ON ts.parcel_number = p.parcel_number"
)

MATCH_SELECT = (
    "p.parcel_number, p.address, p.owner, p.base_zoning_code, p.is_vacant, p.market_value, "
    "round(pv.opportunity_score)::int AS opportunity_score"
)

MATCH_ORDER = "ORDER BY pv.opportunity_score DESC NULLS LAST, p.parcel_number"


def build_where(criteria: SearchCriteria) -> tuple[str, dict[str, Any]]:
    conditions: list[str] = []
    params: dict[str, Any] = {}

    if criteria.exclude_city_owned:
        conditions.append("coalesce(p.is_city_owned, false) = false")
    if criteria.vacant_only:
        conditions.append("coalesce(p.is_vacant, false) = true")
    if criteria.zoning_codes:
        conditions.append("p.base_zoning_code = ANY(:zoning_codes)")
        params["zoning_codes"] = criteria.zoning_codes
    if criteria.zip_code is not None:
        conditions.append("p.zip_code = :zip_code")
        params["zip_code"] = criteria.zip_code
    if criteria.min_market_value is not None:
        conditions.append("p.market_value >= :min_market_value")
        params["min_market_value"] = criteria.min_market_value
    if criteria.max_market_value is not None:
        conditions.append("p.market_value <= :max_market_value")
        params["max_market_value"] = criteria.max_market_value
    if criteria.min_lot_area_sqft is not None:
        conditions.append("p.lot_area_sqft >= :min_lot_area_sqft")
        params["min_lot_area_sqft"] = criteria.min_lot_area_sqft
    if criteria.max_lot_area_sqft is not None:
        conditions.append("p.lot_area_sqft <= :max_lot_area_sqft")
        params["max_lot_area_sqft"] = criteria.max_lot_area_sqft
    if criteria.min_opportunity_score is not None:
        conditions.append("pv.opportunity_score >= :min_opportunity_score")
        params["min_opportunity_score"] = criteria.min_opportunity_score
    if criteria.min_distress_score is not None:
        conditions.append("pd.score >= :min_distress_score")
        params["min_distress_score"] = criteria.min_distress_score
    if criteria.is_delinquent is not None:
        conditions.append("coalesce(ts.is_delinquent, false) = :is_delinquent")
        params["is_delinquent"] = criteria.is_delinquent
    if criteria.in_sheriff_sale is not None:
        conditions.append("coalesce(ts.in_sheriff_sale, false) = :in_sheriff_sale")
        params["in_sheriff_sale"] = criteria.in_sheriff_sale

    where = " AND ".join(conditions) if conditions else "true"
    return where, params


def build_match_sql(criteria: SearchCriteria) -> tuple[str, dict[str, Any]]:
    where, params = build_where(criteria)
    sql = (
        f"SELECT {MATCH_SELECT} {MATCH_BASE} WHERE {where} {MATCH_ORDER} "
        "LIMIT CAST(:match_limit AS integer)"
    )
    return sql, params


def new_match_numbers(current: Iterable[str], seen: Iterable[str]) -> list[str]:
    seen_set = set(seen)
    ordered_new: list[str] = []
    emitted: set[str] = set()
    for number in current:
        if number not in seen_set and number not in emitted:
            ordered_new.append(number)
            emitted.add(number)
    return ordered_new
