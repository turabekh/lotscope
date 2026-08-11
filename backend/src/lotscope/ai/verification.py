from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.derivation import PHILLYCODE_SOURCE, SourceProvision, derive
from lotscope.provisions.service import provisions_for_title, title_numbers

_ACTUAL_BY_TITLE = text(
    "SELECT doc_metadata->>'title_number' AS title_number, count(*) AS documents "
    "FROM document WHERE source = :source AND doc_metadata ? 'title_number' "
    "GROUP BY 1"
)
_LATEST_LEDGER = text(
    "SELECT DISTINCT ON (title_number) title_number, status, derivation_version, finished_at "
    "FROM derivation_run WHERE source = :source "
    "ORDER BY title_number, finished_at DESC"
)
_VERSIONS = text(
    "SELECT doc_metadata->>'title_number' AS title_number, "
    "doc_metadata->>'derivation_version' AS derivation_version, count(*) AS documents "
    "FROM document WHERE source = :source AND doc_metadata ? 'title_number' "
    "GROUP BY 1, 2"
)


def _title_sort_key(title_number: str) -> tuple[float, str]:
    try:
        return (float(title_number), title_number)
    except ValueError:
        return (float("inf"), title_number)


class TitleVerification(BaseModel):
    title_number: str
    expected: int
    actual: int
    shortfall: int
    ledger_status: str | None
    ledger_version: str | None
    document_versions: list[str]

    @property
    def claimed_complete(self) -> bool:
        return self.ledger_status == "succeeded"


class VerificationReport(BaseModel):
    market_code: str
    derivation_version: str
    titles: list[TitleVerification]
    require_complete: bool

    @property
    def expected(self) -> int:
        return sum(title.expected for title in self.titles)

    @property
    def actual(self) -> int:
        return sum(title.actual for title in self.titles)

    @property
    def breached(self) -> list[TitleVerification]:
        return [title for title in self.titles if title.claimed_complete and title.shortfall != 0]

    @property
    def unclaimed(self) -> list[TitleVerification]:
        return [title for title in self.titles if not title.claimed_complete]

    @property
    def stale_versions(self) -> list[TitleVerification]:
        return [
            title
            for title in self.titles
            if any(version != self.derivation_version for version in title.document_versions)
        ]

    @property
    def ok(self) -> bool:
        if self.breached or self.stale_versions:
            return False
        return not (self.require_complete and any(title.shortfall != 0 for title in self.titles))


async def expected_documents_for_title(
    session: AsyncSession, market_code: str, title_number: str
) -> int:
    rows = await provisions_for_title(session, market_code, title_number)
    provisions = [
        SourceProvision(
            id=row.id,
            cite=row.cite,
            kind=row.kind,
            title_number=row.title_number,
            parent=row.parent,
            ordinal=row.ordinal,
            path=row.path,
            heading=row.heading,
            text=row.text,
            source_version=row.source_version,
            table_data=row.table_data,
        )
        for row in rows
    ]
    documents, _report = derive(provisions)
    return len(documents)


async def verify_derivation(
    session: AsyncSession,
    *,
    market_code: str,
    derivation_version: str,
    require_complete: bool = False,
) -> VerificationReport:
    wanted = await title_numbers(session, market_code)

    actual_rows = (await session.execute(_ACTUAL_BY_TITLE, {"source": PHILLYCODE_SOURCE})).all()
    actual = {row.title_number: row.documents for row in actual_rows}

    ledger_rows = (await session.execute(_LATEST_LEDGER, {"source": PHILLYCODE_SOURCE})).all()
    ledger = {row.title_number: row for row in ledger_rows}

    version_rows = (await session.execute(_VERSIONS, {"source": PHILLYCODE_SOURCE})).all()
    versions: dict[str, list[str]] = {}
    for row in version_rows:
        versions.setdefault(row.title_number, []).append(row.derivation_version)

    titles: list[TitleVerification] = []
    for title_number in sorted(wanted, key=_title_sort_key):
        expected = await expected_documents_for_title(session, market_code, title_number)
        found = actual.get(title_number, 0)
        entry = ledger.get(title_number)
        titles.append(
            TitleVerification(
                title_number=title_number,
                expected=expected,
                actual=found,
                shortfall=expected - found,
                ledger_status=entry.status if entry else None,
                ledger_version=entry.derivation_version if entry else None,
                document_versions=sorted(versions.get(title_number, [])),
            )
        )

    return VerificationReport(
        market_code=market_code,
        derivation_version=derivation_version,
        titles=titles,
        require_complete=require_complete,
    )
