_PUBLIC_OWNER_PREFIXES = (
    "CITY OF PHILA",
    "PHILADELPHIA HOUSING",
    "PHDC",
)

_PUBLIC_OWNER_FRAGMENTS = (
    "LAND BANK",
    "REDEVELOPMENT AUTHORITY",
)

_PRIVATE_ENTITY_MARKERS = ("LLC",)


def is_public_owner(owner: str | None) -> bool:
    if owner is None:
        return False
    normalized = " ".join(owner.upper().split())
    if not normalized:
        return False
    if any(marker in normalized for marker in _PRIVATE_ENTITY_MARKERS):
        return False
    if normalized.startswith(_PUBLIC_OWNER_PREFIXES):
        return True
    return any(fragment in normalized for fragment in _PUBLIC_OWNER_FRAGMENTS)
