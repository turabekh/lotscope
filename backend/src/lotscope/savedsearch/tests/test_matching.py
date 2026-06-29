from lotscope.savedsearch.matching import build_match_sql, build_where, new_match_numbers
from lotscope.savedsearch.schemas import SearchCriteria


def test_empty_criteria_excludes_city_owned_by_default() -> None:
    where, params = build_where(SearchCriteria())
    assert where == "coalesce(p.is_city_owned, false) = false"
    assert params == {}


def test_no_conditions_when_city_owned_allowed() -> None:
    where, params = build_where(SearchCriteria(exclude_city_owned=False))
    assert where == "true"
    assert params == {}


def test_all_filters_are_parametrized() -> None:
    criteria = SearchCriteria(
        vacant_only=True,
        zoning_codes=["rsa-5", "RM-1"],
        zip_code="19147",
        min_market_value=10000,
        max_market_value=200000,
        min_lot_area_sqft=900,
        max_lot_area_sqft=5000,
        min_opportunity_score=60,
        min_distress_score=40,
        is_delinquent=True,
        in_sheriff_sale=False,
    )
    where, params = build_where(criteria)

    assert "coalesce(p.is_vacant, false) = true" in where
    assert "p.base_zoning_code = ANY(:zoning_codes)" in where
    assert params["zoning_codes"] == ["RSA-5", "RM-1"]
    assert params["zip_code"] == "19147"
    assert params["min_market_value"] == 10000
    assert params["max_market_value"] == 200000
    assert params["min_lot_area_sqft"] == 900
    assert params["max_lot_area_sqft"] == 5000
    assert params["min_opportunity_score"] == 60
    assert params["min_distress_score"] == 40
    assert params["is_delinquent"] is True
    assert params["in_sheriff_sale"] is False
    assert ":zip_code" in where
    assert "19147" not in where


def test_zoning_codes_normalized_and_deduped() -> None:
    criteria = SearchCriteria(zoning_codes=[" rsa-5 ", "RSA-5", "", "rm-1"])
    assert criteria.zoning_codes == ["RSA-5", "RM-1"]


def test_build_match_sql_has_limit_placeholder() -> None:
    sql, _ = build_match_sql(SearchCriteria(vacant_only=True))
    assert "LIMIT CAST(:match_limit AS integer)" in sql
    assert "FROM parcel p" in sql


def test_new_match_numbers_diffs_against_seen_preserving_order() -> None:
    current = ["003", "001", "004", "002"]
    seen = {"001", "002"}
    assert new_match_numbers(current, seen) == ["003", "004"]


def test_new_match_numbers_dedupes_current() -> None:
    assert new_match_numbers(["a", "a", "b"], set()) == ["a", "b"]


def test_new_match_numbers_empty_when_all_seen() -> None:
    assert new_match_numbers(["a", "b"], {"a", "b"}) == []
