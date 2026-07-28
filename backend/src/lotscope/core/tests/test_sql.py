from lotscope.core.sql import future_sale_exclusion_sql, resolved_zoning_code_sql


def test_future_sale_exclusion_bounds_the_alias_against_today() -> None:
    assert future_sale_exclusion_sql("s") == "s.sale_date <= CURRENT_DATE"
    assert future_sale_exclusion_sql("pkg") == "pkg.sale_date <= CURRENT_DATE"


def test_resolved_zoning_code_sql_single_alias() -> None:
    assert (
        resolved_zoning_code_sql("p")
        == "coalesce(nullif(p.base_zoning_code, ''), p.resolved_zoning_code)"
    )


def test_resolved_zoning_code_sql_distinct_resolved_alias() -> None:
    assert (
        resolved_zoning_code_sql("pa", "p")
        == "coalesce(nullif(pa.base_zoning_code, ''), p.resolved_zoning_code)"
    )
