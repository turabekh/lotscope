from dataclasses import dataclass

PHILADELPHIA_MARKET_CODE = "phl"
TITLE_14_SOURCE = "title14"
ZONING_SOURCE = "zoning"
PHILLYCODE_SOURCE = "phillycode"
DEFAULT_TITLE_SCOPE = ["14"]


@dataclass(frozen=True)
class RetrievalScope:
    source: str
    market: str | None
    titles: list[str] | None


def zoning_retrieval_scope(
    market_code: str,
    *,
    source_override: str | None = None,
    titles: list[str] | None = None,
) -> RetrievalScope:
    if market_code != PHILADELPHIA_MARKET_CODE:
        return RetrievalScope(source=ZONING_SOURCE, market=market_code, titles=None)
    if source_override != PHILLYCODE_SOURCE:
        return RetrievalScope(source=TITLE_14_SOURCE, market=None, titles=None)
    return RetrievalScope(
        source=PHILLYCODE_SOURCE,
        market=None,
        titles=list(titles) if titles else list(DEFAULT_TITLE_SCOPE),
    )
