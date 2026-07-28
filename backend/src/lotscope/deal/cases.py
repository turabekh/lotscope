from dataclasses import dataclass
from typing import Literal

ScenarioCase = Literal["base", "downside", "upside"]

CASE_VERSION = "c1"

CASES: tuple[ScenarioCase, ...] = ("downside", "base", "upside")


@dataclass(frozen=True)
class CaseDeltas:
    case: ScenarioCase
    label: str
    exit_value_multiplier: float
    construction_cost_multiplier: float
    rationale: str


_DOWNSIDE = CaseDeltas(
    case="downside",
    label="Downside",
    exit_value_multiplier=0.90,
    construction_cost_multiplier=1.10,
    rationale="Finished value 10% below the estimate and construction 10% above it.",
)

_BASE = CaseDeltas(
    case="base",
    label="Base",
    exit_value_multiplier=1.0,
    construction_cost_multiplier=1.0,
    rationale="The estimate as modelled, with no adjustment.",
)

_UPSIDE = CaseDeltas(
    case="upside",
    label="Upside",
    exit_value_multiplier=1.10,
    construction_cost_multiplier=0.95,
    rationale="Finished value 10% above the estimate and construction 5% below it.",
)

_BY_CASE: dict[ScenarioCase, CaseDeltas] = {
    "downside": _DOWNSIDE,
    "base": _BASE,
    "upside": _UPSIDE,
}


def deltas_for(case: ScenarioCase) -> CaseDeltas:
    return _BY_CASE[case]


def all_cases() -> tuple[CaseDeltas, ...]:
    return tuple(_BY_CASE[case] for case in CASES)
