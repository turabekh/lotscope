from collections.abc import Sequence
from enum import StrEnum

from lotscope.core.errors import ValidationError

_MARKET_FLAG = "--market"


class Market(StrEnum):
    philadelphia = "philadelphia"
    harrisburg = "harrisburg"
    pittsburgh = "pittsburgh"
    wilmington = "wilmington"


DEFAULT_MARKET = Market.philadelphia

_SLUG_TO_CODE: dict[str, str] = {
    "philadelphia": "phl",
    "harrisburg": "hbg",
    "pittsburgh": "pgh",
    "wilmington": "wlm",
}

MARKET_SLUGS: frozenset[str] = frozenset(_SLUG_TO_CODE)
MARKET_CODES: frozenset[str] = frozenset(_SLUG_TO_CODE.values())


def market_code(value: str) -> str:
    resolved = _SLUG_TO_CODE.get(value)
    if resolved is not None:
        return resolved
    if value in MARKET_CODES:
        return value
    known = ", ".join(sorted(MARKET_SLUGS | MARKET_CODES))
    raise ValidationError(f"Unknown market {value!r}. Known markets: {known}.")


def market_argument(argv: Sequence[str]) -> str | None:
    args = list(argv)
    if _MARKET_FLAG not in args:
        return None
    position = args.index(_MARKET_FLAG) + 1
    if position >= len(args):
        raise ValidationError(f"{_MARKET_FLAG} requires a market slug or code.")
    return market_code(args[position])
