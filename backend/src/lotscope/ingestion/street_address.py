import re

_PUNCTUATION = re.compile(r"[.,#]")
_WHITESPACE = re.compile(r"\s+")
_UNIT = re.compile(r"\b(?:APT|UNIT|STE|SUITE|FL|FLOOR|RM|ROOM)\b.*$")

_SUFFIXES = {
    "STREET": "ST",
    "AVENUE": "AVE",
    "ROAD": "RD",
    "BOULEVARD": "BLVD",
    "DRIVE": "DR",
    "LANE": "LN",
    "PLACE": "PL",
    "COURT": "CT",
    "TERRACE": "TER",
    "PARKWAY": "PKWY",
    "CIRCLE": "CIR",
    "SQUARE": "SQ",
    "HIGHWAY": "HWY",
}

_DIRECTIONS = {
    "NORTH": "N",
    "SOUTH": "S",
    "EAST": "E",
    "WEST": "W",
    "NORTHEAST": "NE",
    "NORTHWEST": "NW",
    "SOUTHEAST": "SE",
    "SOUTHWEST": "SW",
}


def normalize_street_address(raw: str | None) -> str | None:
    if not raw:
        return None
    upper = _PUNCTUATION.sub(" ", raw).upper()
    upper = _UNIT.sub("", upper)
    tokens = [
        _SUFFIXES.get(token, _DIRECTIONS.get(token, token))
        for token in _WHITESPACE.sub(" ", upper).strip().split()
    ]
    return " ".join(tokens) or None
