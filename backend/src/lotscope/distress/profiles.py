from dataclasses import dataclass

from lotscope.core.errors import ConfigurationError


class UnknownMarketProfileError(ConfigurationError):
    default_message = "No distress scoring profile is registered for this market."


@dataclass(frozen=True)
class DistressScoringProfile:
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


DISTRESS_PROFILE = DistressScoringProfile(
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
