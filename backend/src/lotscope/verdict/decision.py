from dataclasses import dataclass
from typing import Literal

from lotscope.core.provenance import FieldProvenance

DECISION_VERSION = "d2"

Recommendation = Literal[
    "strong_candidate",
    "worth_investigating",
    "high_entitlement_risk",
    "economics_unattractive",
    "insufficient_data",
    "likely_pass",
]

CRITICAL_FIELDS: tuple[str, ...] = ("can_build_by_right", "by_right_units")

STRONG_MARGIN = 0.20
VIABLE_MARGIN = 0.10
ELEVATED_RISK_SCORE = 60.0
DEAL_KILLER_LIMIT = 3

_SEVERITY_RANK: dict[str, int] = {"high": 0, "medium": 1, "low": 2, "info": 3}

_DECISION_IMPACT: tuple[str, ...] = (
    "master_plan_required",
    "no_street_access",
    "public_ownership",
    "tax_delinquent",
    "sheriff_sale",
    "flood_zone",
    "historic_district",
)


@dataclass(frozen=True)
class ScreeningDecision:
    recommendation: Recommendation
    reason: str
    decision_version: str = DECISION_VERSION


def _unavailable_critical(field_trust: dict[str, FieldProvenance]) -> list[str]:
    return [
        name
        for name in CRITICAL_FIELDS
        if field_trust.get(name) is None or field_trust[name].status == "unavailable"
    ]


def _impact_rank(code: str) -> int:
    return _DECISION_IMPACT.index(code) if code in _DECISION_IMPACT else len(_DECISION_IMPACT)


def rank_deal_killers(risk_flags: list[dict[str, object]]) -> list[dict[str, object]]:
    ranked = sorted(
        risk_flags,
        key=lambda flag: (
            _SEVERITY_RANK.get(str(flag.get("severity")), len(_SEVERITY_RANK)),
            _impact_rank(str(flag.get("code"))),
            str(flag.get("code")),
        ),
    )
    return ranked[:DEAL_KILLER_LIMIT]


def _risk_clause(risk_score: float | None, risk_flag_count: int) -> str:
    if risk_flag_count <= 0:
        return "no risk flags recorded"
    plural = "flag" if risk_flag_count == 1 else "flags"
    if risk_score is None:
        return f"{risk_flag_count} risk {plural} recorded - review them before committing"
    return (
        f"a risk score of {risk_score:.0f}/100 below the elevated threshold, but "
        f"{risk_flag_count} {plural} recorded - review them before committing"
    )


def decide(
    *,
    field_trust: dict[str, FieldProvenance],
    can_build_by_right: bool | None,
    needs_variance: bool | None,
    requires_master_plan: bool,
    est_margin: float | None,
    deal_infeasible: bool,
    risk_score: float | None,
    land_value_modelled: bool = True,
    land_value_is_wide_area: bool = False,
    risk_flag_count: int = 0,
) -> ScreeningDecision:
    if requires_master_plan:
        return ScreeningDecision(
            recommendation="high_entitlement_risk",
            reason="A master plan appears to be required, which is an entitlement process before "
            "any by-right path.",
        )

    missing = _unavailable_critical(field_trust)
    if missing:
        return ScreeningDecision(
            recommendation="insufficient_data",
            reason=(
                "Core buildability could not be established for this parcel "
                f"({', '.join(missing)}), so no screening result is offered."
            ),
        )

    if can_build_by_right is False and needs_variance is True:
        return ScreeningDecision(
            recommendation="high_entitlement_risk",
            reason="The base-district standards are not met, so a variance would be needed before "
            "this parcel can be developed as modelled.",
        )

    if can_build_by_right is not True:
        return ScreeningDecision(
            recommendation="likely_pass",
            reason="The parcel does not appear dimensionally eligible under its base district and "
            "no variance path is indicated.",
        )

    if deal_infeasible and (est_margin is None or est_margin < VIABLE_MARGIN):
        return ScreeningDecision(
            recommendation="economics_unattractive",
            reason="Even at a land price of $0 the modelled build does not reach the target "
            "margin, so there is no acquisition price that makes this work as modelled.",
        )

    if est_margin is not None and est_margin < VIABLE_MARGIN:
        return ScreeningDecision(
            recommendation="economics_unattractive",
            reason=f"Projected margin of {est_margin:.0%} is below the {VIABLE_MARGIN:.0%} "
            "screening threshold under current assumptions.",
        )

    elevated_risk = risk_score is not None and risk_score >= ELEVATED_RISK_SCORE
    if est_margin is not None and est_margin >= STRONG_MARGIN and not elevated_risk:
        if land_value_is_wide_area:
            return ScreeningDecision(
                recommendation="worth_investigating",
                reason=(
                    f"Projected margin of {est_margin:.0%} rests on land sales from a wider "
                    "search - none were found close by, so the price side is a rough guide "
                    "rather than a market read for this block."
                ),
            )
        if not land_value_modelled:
            return ScreeningDecision(
                recommendation="worth_investigating",
                reason=(
                    f"Projected margin of {est_margin:.0%} rests on the assessed value - no "
                    "comparable land sales were available to price the land, so the margin is "
                    "not yet evidence of a strong deal."
                ),
            )
        return ScreeningDecision(
            recommendation="strong_candidate",
            reason=(
                f"Appears dimensionally eligible with a projected margin of {est_margin:.0%} "
                f"and {_risk_clause(risk_score, risk_flag_count)}."
            ),
        )

    if deal_infeasible and est_margin is not None:
        return ScreeningDecision(
            recommendation="worth_investigating",
            reason=(
                f"Projected margin of {est_margin:.0%} clears the {VIABLE_MARGIN:.0%} screening "
                "threshold at the modelled land price, but the build does not reach the target "
                "margin at any land price - the headroom comes from the price paid, not the build."
            ),
        )

    return ScreeningDecision(
        recommendation="worth_investigating",
        reason="Appears dimensionally eligible, but the economics or risk signals are mixed enough "
        "to warrant a closer look before committing time.",
    )
