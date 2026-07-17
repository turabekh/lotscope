from enum import StrEnum

from lotscope.core.errors import ValidationError


class Market(StrEnum):
    philadelphia = "philadelphia"
    harrisburg = "harrisburg"
    pittsburgh = "pittsburgh"


DEFAULT_MARKET = Market.philadelphia

_SLUG_TO_CODE: dict[str, str] = {
    "philadelphia": "phl",
    "harrisburg": "hbg",
    "pittsburgh": "pgh",
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
