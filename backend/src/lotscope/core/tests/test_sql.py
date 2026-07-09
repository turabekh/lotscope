from lotscope.core.sql import resolved_zoning_code_sql


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
