from dataclasses import dataclass
from typing import Literal

from lotscope.core.names import normalize_party_key

MatchStrength = Literal["exact", "partial", "none"]

PARTY_DELIMITER = ";"

_MIN_SHARED_TOKENS = 2
_STRENGTH_RANK: dict[MatchStrength, int] = {"none": 0, "partial": 1, "exact": 2}
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


def _parties(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(
        party for party in (piece.strip() for piece in value.split(PARTY_DELIMITER)) if party
    )


def _match_one_party(left: str, right: str) -> PartyMatch:
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


def match_parties(left: str | None, right: str | None) -> PartyMatch:
    best = PartyMatch("none", ())
    for left_party in _parties(left):
        for right_party in _parties(right):
            candidate = _match_one_party(left_party, right_party)
            if _STRENGTH_RANK[candidate.strength] > _STRENGTH_RANK[best.strength]:
                best = candidate
                if best.strength == "exact":
                    return best
    return best
