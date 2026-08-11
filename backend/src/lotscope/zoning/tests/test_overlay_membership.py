from lotscope.zoning.overlay_membership import (
    _CLEAR_SQL,
    _DIVERGENCE_SQL,
    _REFRESH_SQL,
)


def test_refresh_is_scoped_to_one_market() -> None:
    assert ":market_code" in str(_CLEAR_SQL)
    assert ":market_code" in str(_REFRESH_SQL)


def test_refresh_only_materializes_parcels_that_have_geometry() -> None:
    assert "geom_local IS NOT NULL" in str(_REFRESH_SQL)


def test_refresh_carries_the_code_section_the_effective_standard_joins_on() -> None:
    assert "zo.code_section" in str(_REFRESH_SQL)


def test_divergence_check_compares_the_live_join_against_the_materialized_table() -> None:
    body = str(_DIVERGENCE_SQL)

    assert "ST_Intersects" in body
    assert "EXCEPT" in body
    assert "parcel_overlay" in body
