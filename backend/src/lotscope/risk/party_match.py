from dataclasses import dataclass
from typing import Literal

from lotscope.core.names import normalize_party_key

MatchStrength = Literal["exact", "partial", "none"]

_MIN_SHARED_TOKENS = 2
_NOISE_TOKENS = frozenset(
    {"THE", "AND", "ET", "AL", "JR", "SR", "II", "III", "IV", "MR", "MRS", "MS"}
)


@dataclass(frozen=True)
class PartyMatch:
    strength: MatchStrength
    shared_tokens: tuple[str, ...]


def _tokens(name: str | None) -> frozenset[str]:
    key = normalize_party_key(name)
    if key is None:
        return frozenset()
    return frozenset(token for token in key.split() if token and token not in _NOISE_TOKENS)


def match_parties(left: str | None, right: str | None) -> PartyMatch:
    left_key = normalize_party_key(left)
    right_key = normalize_party_key(right)
    if left_key is None or right_key is None:
        return PartyMatch("none", ())
    if left_key == right_key:
        return PartyMatch("exact", tuple(sorted(_tokens(left))))

    shared = _tokens(left) & _tokens(right)
    if len(shared) >= _MIN_SHARED_TOKENS:
        return PartyMatch("partial", tuple(sorted(shared)))
    return PartyMatch("none", ())
