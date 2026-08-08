import re

DISTRICT_PREFIXES = (
    "RSD",
    "RSA",
    "RTA",
    "RMX",
    "RM",
    "CMX",
    "CA",
    "ICMX",
    "IRMX",
    "SPPOA",
    "SPINS",
    "SPENT",
    "SPAIR",
    "SPSTA",
    "I",
)

_DISTRICT_RE = re.compile(
    r"\b(" + "|".join(sorted(DISTRICT_PREFIXES, key=len, reverse=True)) + r")-?(\d+(?:\.\d+)?)\b",
    re.IGNORECASE,
)
_CITE_RE = re.compile(r"\b(\d{1,2}(?:\.\d)?-\d{2,4}(?:\([^)\s]{1,8}\))*)")


def extract_districts(query: str) -> list[str]:
    seen: dict[str, None] = {}
    for prefix, number in _DISTRICT_RE.findall(query):
        seen.setdefault(f"{prefix.upper()}-{number}", None)
    return list(seen)


def extract_cites(query: str) -> list[str]:
    seen: dict[str, None] = {}
    for match in _CITE_RE.findall(query):
        seen.setdefault(match, None)
    return list(seen)


def lexical_terms(query: str) -> list[str]:
    return extract_cites(query) + extract_districts(query)
