from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from lotscope.deal.assumptions import (
    Assumption,
    AssumptionSet,
    UnavailableInputError,
    money,
    resolve,
)

MAO_FORMULA = (
    "max_allowable_offer = (exit_value x (1 - selling_costs)) "
    "- construction_costs - soft_costs - (exit_value x target_margin)"
)

MAO_EXCLUSIONS: tuple[str, ...] = (
    "financing interest, points, and loan fees",
    "carrying costs during entitlement, construction, and sale",
    "transfer taxes on acquisition and on exit",
    "title, closing, survey, legal, and environmental diligence",
    "site work, demolition, utility connections, and excavation premiums",
    "construction contingency",
    "brokerage on acquisition",
)


@dataclass(frozen=True)
class MaoDisclosure:
    formula: str
    target_margin: float | None
    inputs: dict[str, str]
    exclusions: tuple[str, ...]
    unavailable_inputs: tuple[str, ...]
    computed_at: datetime


def build_assumption_set(
    *,
    settings: Any,
    user_overrides: dict[str, float] | None = None,
    scenario_overrides: dict[str, float] | None = None,
) -> AssumptionSet:
    user = user_overrides or {}
    scenario = scenario_overrides or {}

    def _resolve(
        name: str, group: str, unit: str, platform: float | None = None, **kw: Any
    ) -> Assumption:
        return resolve(
            name,
            group,  # type: ignore[arg-type]
            unit,  # type: ignore[arg-type]
            platform_default=platform,
            user_override=user.get(name),
            scenario_override=scenario.get(name),
            **kw,
        )

    items = [
        _resolve(
            "default_unit_sqft", "development_program", "sqft", settings.deal_default_unit_sqft
        ),
        _resolve("max_unit_sqft", "development_program", "sqft", settings.deal_max_unit_sqft),
        _resolve(
            "construction_cost_per_sqft",
            "construction",
            "money",
            settings.deal_construction_cost_per_sqft,
        ),
        _resolve("soft_cost_pct", "soft_costs", "fraction", settings.deal_soft_cost_pct),
        _resolve("selling_cost_pct", "exit", "fraction", settings.deal_selling_cost_pct),
        _resolve("target_margin", "exit", "fraction", settings.deal_target_margin),
        _resolve(
            "interest_rate",
            "financing_and_time",
            "fraction",
            limitations="No Philadelphia financing rate has been supplied, so interest is not "
            "modelled and the result excludes carrying cost.",
        ),
        _resolve(
            "loan_points",
            "financing_and_time",
            "fraction",
            limitations="No loan-points assumption has been supplied.",
        ),
        _resolve(
            "construction_months",
            "financing_and_time",
            "months",
            limitations="No construction duration has been supplied, so carrying cost over the "
            "build period is not modelled.",
        ),
        _resolve(
            "entitlement_months",
            "financing_and_time",
            "months",
            limitations="No entitlement duration has been supplied.",
        ),
        _resolve(
            "acquisition_transfer_tax_pct",
            "acquisition",
            "fraction",
            limitations="No transfer-tax rate has been supplied for this market.",
        ),
        _resolve(
            "exit_transfer_tax_pct",
            "exit",
            "fraction",
            limitations="No exit transfer-tax rate has been supplied for this market.",
        ),
    ]
    return AssumptionSet(items={item.name: item for item in items})


def mao_disclosure(assumptions: AssumptionSet, computed_at: datetime) -> MaoDisclosure:
    target = assumptions.get("target_margin")
    inputs = {
        item.name: f"{item.value} ({item.origin})"
        for item in assumptions.items.values()
        if item.available
    }
    return MaoDisclosure(
        formula=MAO_FORMULA,
        target_margin=float(target.require()) if target.available else None,
        inputs=inputs,
        exclusions=MAO_EXCLUSIONS,
        unavailable_inputs=tuple(
            sorted(name for name, item in assumptions.items.items() if not item.available)
        ),
        computed_at=computed_at,
    )


def require_money(assumptions: AssumptionSet, name: str) -> Decimal:
    value = assumptions.get(name).require()
    return money(value)


def missing_required(assumptions: AssumptionSet, names: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(name for name in names if not assumptions.get(name).available)


def guard_required(assumptions: AssumptionSet, names: tuple[str, ...]) -> None:
    missing = missing_required(assumptions, names)
    if missing:
        raise UnavailableInputError(
            "Required underwriting inputs are unavailable: " + ", ".join(missing)
        )
