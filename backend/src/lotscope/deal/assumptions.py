from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from lotscope.core.provenance import DefaultOrigin

AssumptionGroup = Literal[
    "development_program",
    "acquisition",
    "construction",
    "soft_costs",
    "financing_and_time",
    "exit",
]

_CENTS = Decimal("0.01")


class UnavailableInputError(ValueError):
    pass


def money(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(_CENTS, rounding=ROUND_HALF_UP)


def fraction(value: float) -> float:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"A percentage assumption must be a fraction in [0, 1], got {value!r}.")
    return value


@dataclass(frozen=True)
class Assumption:
    name: str
    group: AssumptionGroup
    value: Decimal | float | int | None
    origin: DefaultOrigin
    unit: Literal["money", "fraction", "count", "months", "sqft"]
    limitations: str | None = None

    @property
    def available(self) -> bool:
        return self.value is not None

    def require(self) -> Decimal | float | int:
        if self.value is None:
            raise UnavailableInputError(
                f"{self.name} is unavailable, so any figure depending on it cannot be calculated."
            )
        return self.value


@dataclass(frozen=True)
class AssumptionSet:
    items: dict[str, Assumption] = field(default_factory=dict)

    def get(self, name: str) -> Assumption:
        assumption = self.items.get(name)
        if assumption is None:
            raise KeyError(f"No assumption named {name!r} is registered.")
        return assumption

    def unavailable_in(self, group: AssumptionGroup) -> list[str]:
        return sorted(
            name for name, item in self.items.items() if item.group == group and not item.available
        )

    def by_group(self, group: AssumptionGroup) -> list[Assumption]:
        return [item for item in self.items.values() if item.group == group]

    def group_total(self, group: AssumptionGroup) -> Decimal | None:
        items = [item for item in self.by_group(group) if item.unit == "money"]
        if not items or any(not item.available for item in items):
            return None
        return money(sum(Decimal(str(item.require())) for item in items))

    def overridden(self) -> list[str]:
        return sorted(name for name, item in self.items.items() if item.origin == "user_override")


def resolve(
    name: str,
    group: AssumptionGroup,
    unit: Literal["money", "fraction", "count", "months", "sqft"],
    *,
    platform_default: float | None = None,
    market_default: float | None = None,
    parcel_derived: float | None = None,
    user_override: float | None = None,
    limitations: str | None = None,
) -> Assumption:
    for candidate, origin in (
        (user_override, "user_override"),
        (parcel_derived, "derived"),
        (market_default, "market_default"),
        (platform_default, "platform_default"),
    ):
        if candidate is not None:
            value: Decimal | float = (
                money(candidate)
                if unit == "money"
                else fraction(candidate)
                if unit == "fraction"
                else candidate
            )
            return Assumption(
                name=name,
                group=group,
                value=value,
                origin=origin,  # type: ignore[arg-type]
                unit=unit,
                limitations=limitations,
            )
    return Assumption(
        name=name,
        group=group,
        value=None,
        origin="platform_default",
        unit=unit,
        limitations=limitations
        or f"No {name.replace('_', ' ')} is available for this market, so it was not assumed.",
    )
