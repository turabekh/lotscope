from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.derivation import PHILLYCODE_SOURCE
from lotscope.core.market import MARKET_CODE

MINIMUM_PROVISIONS = 25_000
MINIMUM_COVERAGE_PCT = 99.0

_BY_TITLE = text(
    "WITH represented AS ("
    "  SELECT doc_metadata->>'title_number' AS title_number, "
    "         doc_metadata->>'provision_id' AS provision_id "
    "  FROM document WHERE source = :source "
    "  UNION "
    "  SELECT doc_metadata->>'title_number', "
    "         jsonb_array_elements_text("
    "           coalesce(doc_metadata->'folded_provision_ids', '[]'::jsonb))"
    "  FROM document WHERE source = :source"
    "), docs AS ("
    "  SELECT doc_metadata->>'title_number' AS title_number, "
    "         count(*) AS documents, "
    "         count(embedding) AS embedded "
    "  FROM document WHERE source = :source GROUP BY 1"
    ") "
    "SELECT p.title_number, "
    "       count(*) AS provisions, "
    "       count(r.provision_id) AS represented, "
    "       coalesce(max(d.documents), 0) AS documents, "
    "       coalesce(max(d.embedded), 0) AS embedded "
    "FROM code_provision p "
    "LEFT JOIN represented r "
    "  ON r.provision_id = p.id AND r.title_number = p.title_number "
    "LEFT JOIN docs d ON d.title_number = p.title_number "
    "WHERE p.market_code = :market_code "
    "GROUP BY p.title_number"
)

_LAST_LOADED = text("SELECT max(loaded_at) FROM code_provision WHERE market_code = :market_code")


@dataclass(frozen=True)
class TitleCoverage:
    title_number: str
    provisions: int
    represented: int
    documents: int
    embedded: int

    @property
    def coverage_pct(self) -> float:
        return 100.0 * self.embedded / self.documents if self.documents else 0.0

    @property
    def represented_pct(self) -> float:
        return 100.0 * self.represented / self.provisions if self.provisions else 0.0


@dataclass(frozen=True)
class CorpusHealth:
    titles: list[TitleCoverage]
    last_loaded_at: datetime | None

    @property
    def total_provisions(self) -> int:
        return sum(title.provisions for title in self.titles)

    @property
    def total_documents(self) -> int:
        return sum(title.documents for title in self.titles)

    @property
    def total_embedded(self) -> int:
        return sum(title.embedded for title in self.titles)

    @property
    def total_represented(self) -> int:
        return sum(title.represented for title in self.titles)

    @property
    def coverage_pct(self) -> float:
        total = self.total_documents
        return 100.0 * self.total_embedded / total if total else 0.0

    @property
    def represented_pct(self) -> float:
        total = self.total_provisions
        return 100.0 * self.total_represented / total if total else 0.0

    @property
    def healthy(self) -> bool:
        return (
            self.total_provisions >= MINIMUM_PROVISIONS
            and self.coverage_pct >= MINIMUM_COVERAGE_PCT
        )


def _title_sort_key(title_number: str) -> tuple[int, float]:
    try:
        return (0, float(title_number))
    except ValueError:
        return (1, 0.0)


async def corpus_health(session: AsyncSession, *, market_code: str = MARKET_CODE) -> CorpusHealth:
    rows = (
        await session.execute(_BY_TITLE, {"source": PHILLYCODE_SOURCE, "market_code": market_code})
    ).all()
    titles = sorted(
        (
            TitleCoverage(
                title_number=row.title_number,
                provisions=int(row.provisions),
                represented=int(row.represented),
                documents=int(row.documents),
                embedded=int(row.embedded),
            )
            for row in rows
        ),
        key=lambda title: _title_sort_key(title.title_number),
    )
    last_loaded = await session.scalar(_LAST_LOADED, {"market_code": market_code})
    return CorpusHealth(titles=titles, last_loaded_at=last_loaded)
