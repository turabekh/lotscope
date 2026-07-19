from dataclasses import dataclass, replace

from lotscope.core.errors import ConfigurationError


class UnknownMarketProfileError(ConfigurationError):
    default_message = "No distress scoring profile is registered for this market."


@dataclass(frozen=True)
class DistressScoringProfile:
    profile_id: str
    market: str
    sheriff_sale_weight: int
    delinquent_weight: int
    severe_delinquent_weight: int
    lien_weight: int
    dangerous_weight: int
    violation_weight: int
    demolition_weight: int
    vacant_weight: int
    absentee_weight: int
    long_tenure_weight: int
    portfolio_distress_weight: int
    severe_due: float
    severe_years: int
    long_tenure_years: float
    score_cap: int
    high_tier: int
    medium_tier: int


PHILLY_DISTRESS_V1 = DistressScoringProfile(
    profile_id="philly-distress-v1",
    market="phl",
    sheriff_sale_weight=30,
    delinquent_weight=15,
    severe_delinquent_weight=15,
    lien_weight=10,
    dangerous_weight=15,
    violation_weight=5,
    demolition_weight=5,
    vacant_weight=10,
    absentee_weight=10,
    long_tenure_weight=5,
    portfolio_distress_weight=10,
    severe_due=10000.0,
    severe_years=3,
    long_tenure_years=15.0,
    score_cap=100,
    high_tier=60,
    medium_tier=30,
)

HARRISBURG_DISTRESS_V1 = replace(
    PHILLY_DISTRESS_V1, profile_id="harrisburg-distress-v1", market="hbg"
)

PITTSBURGH_DISTRESS_V1 = replace(
    PHILLY_DISTRESS_V1, profile_id="pittsburgh-distress-v1", market="pgh"
)

WILMINGTON_DISTRESS_V1 = replace(
    PHILLY_DISTRESS_V1, profile_id="wilmington-distress-v1", market="wlm"
)

_REGISTRY: dict[str, DistressScoringProfile] = {
    PHILLY_DISTRESS_V1.market: PHILLY_DISTRESS_V1,
    HARRISBURG_DISTRESS_V1.market: HARRISBURG_DISTRESS_V1,
    PITTSBURGH_DISTRESS_V1.market: PITTSBURGH_DISTRESS_V1,
    WILMINGTON_DISTRESS_V1.market: WILMINGTON_DISTRESS_V1,
}


def profile_for_market(market: str) -> DistressScoringProfile:
    profile = _REGISTRY.get(market)
    if profile is None:
        raise UnknownMarketProfileError(
            f"No distress scoring profile is registered for market '{market}'."
        )
    return profile


def registered_markets() -> frozenset[str]:
    return frozenset(_REGISTRY)
