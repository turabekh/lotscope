from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class Invariant:
    name: str
    claim: str
    sql: str
    tolerated: int = 0


@dataclass(frozen=True)
class InvariantResult:
    invariant: Invariant
    violations: int

    @property
    def breached(self) -> bool:
        return self.violations > self.invariant.tolerated


_MARKET_VERDICTS = (
    "FROM parcel_verdict v JOIN parcel p ON p.parcel_number = v.parcel_number "
    "WHERE p.market_code = :market"
)

INVARIANTS: tuple[Invariant, ...] = (
    Invariant(
        name="strong_candidate_makes_money",
        claim="A parcel recommended as a strong candidate never carries a negative profit.",
        sql=(
            f"SELECT count(*) {_MARKET_VERDICTS} "
            "AND v.recommendation = 'strong_candidate' AND v.est_profit < 0"
        ),
    ),
    Invariant(
        name="viable_margin_is_not_called_unattractive",
        claim=(
            "A parcel clearing the viable-margin screening bar is never recommended as "
            "economically unattractive."
        ),
        sql=(
            f"SELECT count(*) {_MARKET_VERDICTS} "
            "AND v.recommendation = 'economics_unattractive' "
            "AND v.est_margin >= 0.10 AND v.est_profit > 0"
        ),
    ),
    Invariant(
        name="infeasible_implies_margin_below_target",
        claim=(
            "A build that cannot reach the target margin at zero land cost never reports a "
            "margin at or above that target."
        ),
        sql=(
            f"SELECT count(*) {_MARKET_VERDICTS} "
            "AND v.max_allowable_offer = 0 AND v.est_margin >= 0.20"
        ),
    ),
    Invariant(
        name="by_right_is_not_entitlement_risk",
        claim="A parcel buildable by right is never screened as a high entitlement risk.",
        sql=(
            f"SELECT count(*) {_MARKET_VERDICTS} "
            "AND v.can_build_by_right IS TRUE AND v.recommendation = 'high_entitlement_risk'"
        ),
    ),
    Invariant(
        name="by_right_does_not_need_a_variance",
        claim="A parcel buildable by right never simultaneously requires a variance.",
        sql=(
            f"SELECT count(*) {_MARKET_VERDICTS} "
            "AND v.can_build_by_right IS TRUE AND v.needs_variance IS TRUE"
        ),
    ),
    Invariant(
        name="value_range_stays_interpretable",
        claim=(
            "No more than a tenth of valued parcels report a range wider than tenfold, beyond "
            "which the estimate stops being a usable number. Reports the offending count only "
            "once that share is exceeded."
        ),
        sql=(
            "SELECT CASE WHEN count(*) FILTER ("
            "  WHERE v.value_estimate_high > v.value_estimate_low * 10"
            ") > 0.10 * greatest(count(*), 1) "
            "THEN count(*) FILTER (WHERE v.value_estimate_high > v.value_estimate_low * 10) "
            "ELSE 0 END "
            f"{_MARKET_VERDICTS} AND v.value_estimate_low > 0"
        ),
    ),
    Invariant(
        name="a_scored_verdict_carries_provenance",
        claim="Every scored verdict records where it came from and when it was computed.",
        sql=(
            f"SELECT count(*) {_MARKET_VERDICTS} "
            "AND v.opportunity_score IS NOT NULL "
            "AND (v.computed_at IS NULL OR v.sources IS NULL)"
        ),
    ),
)


async def check_invariants(
    session: AsyncSession, market: str, invariants: tuple[Invariant, ...] = INVARIANTS
) -> list[InvariantResult]:
    results: list[InvariantResult] = []
    for invariant in invariants:
        violations = await session.scalar(text(invariant.sql), {"market": market})
        results.append(InvariantResult(invariant=invariant, violations=int(violations or 0)))
    return results


def breaches(results: list[InvariantResult]) -> list[InvariantResult]:
    return [result for result in results if result.breached]
