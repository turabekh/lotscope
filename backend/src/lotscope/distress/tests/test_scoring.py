from lotscope.distress.profiles import PHILLY_DISTRESS_V1
from lotscope.distress.scoring import DistressSignals, is_absentee, score_distress


def test_clean_parcel_scores_zero() -> None:
    result = score_distress(DistressSignals(), PHILLY_DISTRESS_V1)
    assert result.score == 0
    assert result.tier == "none"
    assert result.factors == []


def test_city_owned_is_excluded() -> None:
    result = score_distress(
        DistressSignals(is_city_owned=True, in_sheriff_sale=True, is_delinquent=True),
        PHILLY_DISTRESS_V1,
    )
    assert result.score == 0
    assert result.tier == "none"


def test_sheriff_sale_and_severe_delinquency_score_high() -> None:
    result = score_distress(
        DistressSignals(
            in_sheriff_sale=True,
            is_delinquent=True,
            total_due=25000,
            years_owed=5,
        ),
        PHILLY_DISTRESS_V1,
    )
    assert result.score == 60
    assert result.tier == "high"
    codes = {f.code for f in result.factors}
    assert {"sheriff_sale", "tax_delinquent", "severe_delinquency"} <= codes


def test_score_caps_at_100() -> None:
    result = score_distress(
        DistressSignals(
            in_sheriff_sale=True,
            is_delinquent=True,
            total_due=99999,
            years_owed=10,
            lien_count=3,
            has_imminently_dangerous=True,
            demolitions=1,
            is_vacant=True,
            is_absentee_owner=True,
        ),
        PHILLY_DISTRESS_V1,
    )
    assert result.score == 100


def test_mild_delinquency_is_not_severe() -> None:
    result = score_distress(
        DistressSignals(is_delinquent=True, total_due=500, years_owed=1), PHILLY_DISTRESS_V1
    )
    assert result.score == 15
    assert result.tier == "low"


def test_vacant_and_absentee_is_medium() -> None:
    result = score_distress(
        DistressSignals(is_vacant=True, is_absentee_owner=True, violations=2), PHILLY_DISTRESS_V1
    )
    assert result.score == 25
    assert result.tier == "low"


def test_dangerous_outranks_plain_violations() -> None:
    result = score_distress(DistressSignals(has_unsafe=True, violations=5), PHILLY_DISTRESS_V1)
    codes = {f.code for f in result.factors}
    assert "li_dangerous" in codes
    assert "li_violations" not in codes


def test_long_tenure_requires_absentee() -> None:
    resident = score_distress(DistressSignals(years_since_last_sale=20), PHILLY_DISTRESS_V1)
    assert resident.score == 0

    absentee = score_distress(
        DistressSignals(is_absentee_owner=True, years_since_last_sale=20), PHILLY_DISTRESS_V1
    )
    codes = {f.code for f in absentee.factors}
    assert "long_tenure" in codes
    assert absentee.score == 15


def test_short_tenure_does_not_add_long_tenure() -> None:
    result = score_distress(
        DistressSignals(is_absentee_owner=True, years_since_last_sale=5), PHILLY_DISTRESS_V1
    )
    codes = {f.code for f in result.factors}
    assert "long_tenure" not in codes
    assert result.score == 10


def test_tired_landlord_adds_portfolio_distress() -> None:
    result = score_distress(DistressSignals(is_tired_landlord=True), PHILLY_DISTRESS_V1)
    codes = {f.code for f in result.factors}
    assert "portfolio_distress" in codes
    assert result.score == 10


def test_city_owned_excludes_owner_intent_factors() -> None:
    result = score_distress(
        DistressSignals(
            is_city_owned=True,
            is_absentee_owner=True,
            years_since_last_sale=30,
            is_tired_landlord=True,
        ),
        PHILLY_DISTRESS_V1,
    )
    assert result.score == 0


def test_is_absentee_heuristic() -> None:
    assert is_absentee("123 MAIN ST", "456 ELSEWHERE AVE, NEW YORK NY") is True
    assert is_absentee("123 MAIN ST", "123 Main St, Philadelphia PA 19100") is False
    assert is_absentee("123 MAIN ST", None) is False
