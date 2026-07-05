from enum import StrEnum


class Market(StrEnum):
    philadelphia = "philadelphia"
    harrisburg = "harrisburg"


DEFAULT_MARKET = Market.philadelphia

_SLUG_TO_CODE: dict[str, str] = {"philadelphia": "phl", "harrisburg": "hbg"}


def market_code(value: str) -> str:
    return _SLUG_TO_CODE.get(value, value)
