from dataclasses import dataclass

PHILLYCODE_SOURCE = "phillycode"
DEFAULT_TITLE_SCOPE = ["14"]


@dataclass(frozen=True)
class RetrievalScope:
    source: str
    market: str | None
    titles: list[str] | None


def zoning_retrieval_scope(titles: list[str] | None = None) -> RetrievalScope:
    return RetrievalScope(
        source=PHILLYCODE_SOURCE,
        market=None,
        titles=list(titles) if titles else list(DEFAULT_TITLE_SCOPE),
    )
