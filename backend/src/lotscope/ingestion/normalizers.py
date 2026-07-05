import re
from typing import Protocol

_MARKET_KEY_SEP = ":"


class KeyNormalizer(Protocol):
    market: str

    def normalize_local_key(self, raw: str | int | None) -> str | None: ...

    def to_canonical(self, raw: str | int | None) -> str | None: ...


class PhlKeyNormalizer:
    market = "phl"
    _non_digit = re.compile(r"\D")
    _account_length = 9

    def normalize_local_key(self, raw: str | int | None) -> str | None:
        if raw is None:
            return None
        digits = self._non_digit.sub("", str(raw).strip())
        if not digits or len(digits) > self._account_length:
            return None
        return digits.zfill(self._account_length)

    def to_canonical(self, raw: str | int | None) -> str | None:
        local = self.normalize_local_key(raw)
        if local is None:
            return None
        return f"{self.market}{_MARKET_KEY_SEP}{local}"


class HbgKeyNormalizer:
    market = "hbg"
    _whitespace = re.compile(r"\s+")
    _digits_only = re.compile(r"^(\d{2})(\d{3})(\d{3})$")
    _canonical = re.compile(r"^\d{2}-\d{3}-\d{3}(?:-\d+)?$")

    def normalize_local_key(self, raw: str | int | None) -> str | None:
        if raw is None:
            return None
        cleaned = self._whitespace.sub("", str(raw).strip().upper())
        if not cleaned:
            return None
        digits_only = self._digits_only.match(cleaned)
        if digits_only is not None:
            return "-".join(digits_only.groups())
        if self._canonical.match(cleaned):
            return cleaned
        return None

    def to_canonical(self, raw: str | int | None) -> str | None:
        local = self.normalize_local_key(raw)
        if local is None:
            return None
        return f"{self.market}{_MARKET_KEY_SEP}{local}"


KEY_NORMALIZERS: dict[str, KeyNormalizer] = {
    "phl": PhlKeyNormalizer(),
    "hbg": HbgKeyNormalizer(),
}


def get_normalizer(market: str = "phl") -> KeyNormalizer:
    return KEY_NORMALIZERS[market]
