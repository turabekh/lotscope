import dataclasses

import pytest

from lotscope.distress.profiles import (
    HARRISBURG_DISTRESS_V1,
    PHILLY_DISTRESS_V1,
    PITTSBURGH_DISTRESS_V1,
    WILMINGTON_DISTRESS_V1,
    DistressScoringProfile,
    UnknownMarketProfileError,
    profile_for_market,
)
from lotscope.distress.scoring import DistressSignals, score_distress

_LegacyFactor = tuple[str, str, int]


def _legacy_score(s: DistressSignals) -> tuple[int, str, list[_LegacyFactor]]:
    if s.is_city_owned:
        return 0, "none", []
    factors: list[_LegacyFactor] = []
    if s.in_sheriff_sale:
        factors.append(("sheriff_sale", "Sheriff-sale exposure", 30))
    if s.is_delinquent:
        due = s.total_due or 0.0
        factors.append(("tax_delinquent", f"Tax delinquent (${due:,.0f})", 15))
        if due >= 10000.0 or (s.years_owed or 0) >= 3:
            factors.append(("severe_delinquency", "Severe or long-running tax delinquency", 15))
    if (s.lien_count or 0) > 0:
        factors.append(("liens", f"{s.lien_count} tax lien(s)", 10))
    if s.has_imminently_dangerous or s.has_unsafe:
        factors.append(("li_dangerous", "Unsafe or dangerous structure (L&I)", 15))
    elif s.violations > 0:
        factors.append(("li_violations", "Open L&I violations", 5))
    if s.demolitions > 0:
        factors.append(("demolition", "Demolition on record", 5))
    if s.is_vacant:
        factors.append(("vacant", "Vacant lot — owner unlikely to occupy", 10))
    if s.is_absentee_owner:
        factors.append(("absentee", "Absentee owner (out-of-area mailing address)", 10))
    if (
        s.is_absentee_owner
        and s.years_since_last_sale is not None
        and s.years_since_last_sale >= 15.0
    ):
        held = int(s.years_since_last_sale)
        factors.append(("long_tenure", f"Long-tenured absentee owner (~{held} yrs)", 5))
    if s.is_tired_landlord:
        factors.append(("portfolio_distress", "Tired landlord (portfolio-wide violations)", 10))
    score = min(100, sum(weight for _, _, weight in factors))
    tier = "high" if score >= 60 else "medium" if score >= 30 else "low" if score > 0 else "none"
    return score, tier, factors


_MATRIX: dict[str, DistressSignals] = {
    "clean": DistressSignals(),
    "city_owned_zeroes_everything": DistressSignals(
        in_sheriff_sale=True, is_delinquent=True, total_due=50000, is_city_owned=True
    ),
    "sheriff_only": DistressSignals(in_sheriff_sale=True),
    "lien_only": DistressSignals(lien_count=2),
    "vacant_only": DistressSignals(is_vacant=True),
    "absentee_only": DistressSignals(is_absentee_owner=True),
    "demolition_only": DistressSignals(demolitions=1),
    "violations_only": DistressSignals(violations=3),
    "dangerous_suppresses_violations": DistressSignals(has_unsafe=True, violations=3),
    "unsafe_flag": DistressSignals(has_imminently_dangerous=True),
    "portfolio_distress": DistressSignals(is_tired_landlord=True),
    "severe_due_exactly_10000": DistressSignals(is_delinquent=True, total_due=10000.0),
    "just_below_severe_due": DistressSignals(is_delinquent=True, total_due=9999.0, years_owed=2),
    "severe_years_exactly_3": DistressSignals(is_delinquent=True, years_owed=3),
    "just_below_severe_years": DistressSignals(is_delinquent=True, years_owed=2, total_due=500),
    "long_tenure_exactly_15": DistressSignals(is_absentee_owner=True, years_since_last_sale=15.0),
    "just_below_long_tenure": DistressSignals(is_absentee_owner=True, years_since_last_sale=14.999),
    "long_tenure_needs_absentee": DistressSignals(
        is_absentee_owner=False, years_since_last_sale=40.0
    ),
    "tier_high_exactly_60": DistressSignals(
        in_sheriff_sale=True, is_delinquent=True, total_due=20000
    ),
    "tier_just_below_high_55": DistressSignals(
        in_sheriff_sale=True, is_delinquent=True, total_due=500, is_vacant=True
    ),
    "tier_medium_exactly_30": DistressSignals(is_delinquent=True, years_owed=5),
    "tier_just_below_medium_25": DistressSignals(is_delinquent=True, total_due=500, is_vacant=True),
    "cap_engaged_over_100": DistressSignals(
        in_sheriff_sale=True,
        is_delinquent=True,
        total_due=99999,
        lien_count=4,
        has_imminently_dangerous=True,
        demolitions=2,
        is_vacant=True,
        is_absentee_owner=True,
        years_since_last_sale=30.0,
        is_tired_landlord=True,
    ),
}

_PROFILES = [PHILLY_DISTRESS_V1, HARRISBURG_DISTRESS_V1, PITTSBURGH_DISTRESS_V1]


@pytest.mark.parametrize("case", _MATRIX.keys())
@pytest.mark.parametrize("profile", _PROFILES, ids=lambda p: p.profile_id)
def test_profile_scoring_matches_legacy(case: str, profile: DistressScoringProfile) -> None:
    signals = _MATRIX[case]
    legacy_score, legacy_tier, legacy_factors = _legacy_score(signals)
    result = score_distress(signals, profile)
    assert result.score == legacy_score
    assert result.tier == legacy_tier
    assert [(f.code, f.label, f.weight) for f in result.factors] == legacy_factors


def test_severe_tax_edges_are_inclusive() -> None:
    at_dollars = score_distress(_MATRIX["severe_due_exactly_10000"], PHILLY_DISTRESS_V1)
    at_years = score_distress(_MATRIX["severe_years_exactly_3"], PHILLY_DISTRESS_V1)
    below = score_distress(_MATRIX["just_below_severe_due"], PHILLY_DISTRESS_V1)
    assert any(f.code == "severe_delinquency" for f in at_dollars.factors)
    assert any(f.code == "severe_delinquency" for f in at_years.factors)
    assert all(f.code != "severe_delinquency" for f in below.factors)


def test_long_tenure_boundary_is_inclusive_at_15() -> None:
    at = score_distress(_MATRIX["long_tenure_exactly_15"], PHILLY_DISTRESS_V1)
    below = score_distress(_MATRIX["just_below_long_tenure"], PHILLY_DISTRESS_V1)
    assert any(f.code == "long_tenure" for f in at.factors)
    assert all(f.code != "long_tenure" for f in below.factors)


def test_cap_engages_at_100() -> None:
    assert score_distress(_MATRIX["cap_engaged_over_100"], PHILLY_DISTRESS_V1).score == 100


def test_clones_are_identical_to_philly_except_id_and_market() -> None:
    base = dataclasses.replace(PHILLY_DISTRESS_V1, profile_id="x", market="x")
    for clone in (HARRISBURG_DISTRESS_V1, PITTSBURGH_DISTRESS_V1, WILMINGTON_DISTRESS_V1):
        assert dataclasses.replace(clone, profile_id="x", market="x") == base


def test_registry_resolves_each_market() -> None:
    assert profile_for_market("phl") is PHILLY_DISTRESS_V1
    assert profile_for_market("hbg") is HARRISBURG_DISTRESS_V1
    assert profile_for_market("pgh") is PITTSBURGH_DISTRESS_V1
    assert profile_for_market("wlm") is WILMINGTON_DISTRESS_V1


def test_unknown_market_raises() -> None:
    with pytest.raises(UnknownMarketProfileError):
        profile_for_market("zzz")
