import re

_MIN_NAME_TOKEN_LEN = 3
_NAME_STOPWORDS = frozenset(
    {
        "JR",
        "SR",
        "II",
        "III",
        "IV",
        "LLC",
        "INC",
        "CO",
        "CORP",
        "LP",
        "LLP",
        "LTD",
        "TRUST",
        "TRUSTEE",
        "TRUSTEES",
        "ESTATE",
        "ETAL",
        "THE",
        "AND",
    }
)
_NAME_TOKEN_RE = re.compile(r"[A-Z]+")
_KEY_STRIP_RE = re.compile(r"[.,#]")
_KEY_WHITESPACE_RE = re.compile(r"\s+")


def name_tokens(name: str | None) -> frozenset[str]:
    if not name:
        return frozenset()
    tokens = _NAME_TOKEN_RE.findall(name.upper())
    return frozenset(
        token
        for token in tokens
        if len(token) >= _MIN_NAME_TOKEN_LEN and token not in _NAME_STOPWORDS
    )


def is_related_party(grantor: str | None, grantee: str | None) -> bool:
    return bool(name_tokens(grantor) & name_tokens(grantee))


def normalize_party_key(name: str | None) -> str | None:
    if not name:
        return None
    stripped = _KEY_STRIP_RE.sub("", name)
    collapsed = _KEY_WHITESPACE_RE.sub(" ", stripped).strip().upper()
    return collapsed or None
