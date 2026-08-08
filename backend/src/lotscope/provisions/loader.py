import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.errors import LotScopeError
from lotscope.core.logging import get_logger
from lotscope.provisions.models import CodeProvision
from lotscope.provisions.schemas import (
    LoadReport,
    Provision,
    QaSummary,
    TitleLoadResult,
    TitleQa,
)

DEFAULT_ARTIFACT_DIR = Path("data/phillycode")
PHILADELPHIA_MARKET_CODE = "phl"
_SUMMARY_FILE = "qa_summary.json"
_UPSERT_BATCH = 500

logger = get_logger(__name__)


class ProvisionLoadError(LotScopeError):
    default_message = "The Philadelphia Code artifacts could not be loaded."


def _read_json(path: Path) -> Any:
    if not path.exists():
        raise ProvisionLoadError(f"{path.name} is missing from {path.parent}.")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ProvisionLoadError(f"{path.name} is not valid JSON: {error}") from error


def read_qa_summary(directory: Path) -> QaSummary:
    path = directory / _SUMMARY_FILE
    try:
        return QaSummary.model_validate(_read_json(path))
    except PydanticValidationError as error:
        raise ProvisionLoadError(f"{path.name} is not a QA summary: {error}") from error


def read_title_qa(directory: Path, title_number: str) -> TitleQa:
    path = directory / f"qa_title_{title_number}.json"
    try:
        qa = TitleQa.model_validate(_read_json(path))
    except PydanticValidationError as error:
        raise ProvisionLoadError(f"{path.name} is not a per-title QA report: {error}") from error
    if qa.title_number != title_number:
        raise ProvisionLoadError(
            f"{path.name} reports title {qa.title_number!r} rather than {title_number!r}."
        )
    return qa


def _require_artifact(directory: Path, title_number: str) -> Path:
    path = directory / f"title_{title_number}.jsonl"
    if not path.exists():
        raise ProvisionLoadError(
            f"{path.name} is missing, but title {title_number} is listed in {_SUMMARY_FILE}."
        )
    return path


def read_provisions(directory: Path, title_number: str) -> list[Provision]:
    path = _require_artifact(directory, title_number)
    provisions: list[Provision] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            provision = Provision.model_validate(json.loads(stripped))
        except (json.JSONDecodeError, PydanticValidationError) as error:
            raise ProvisionLoadError(
                f"{path.name}:{number} is not a valid provision: {error}"
            ) from error
        if not provision.path or provision.path[0] != title_number:
            raise ProvisionLoadError(
                f"{path.name}:{number} ({provision.id}) carries path root "
                f"{provision.path[0] if provision.path else None!r}, "
                f"but its QA report names title {title_number!r}."
            )
        provisions.append(provision)
    return provisions


def _row(provision: Provision, title_number: str, market_code: str) -> dict[str, Any]:
    return {
        "market_code": market_code,
        "id": provision.id,
        "cite": provision.cite,
        "doc": provision.doc,
        "kind": provision.kind,
        "title_number": title_number,
        "parent": provision.parent,
        "ordinal": provision.order,
        "path": provision.path,
        "heading": provision.heading,
        "text": provision.text,
        "raw_text": provision.raw_text,
        "history": provision.history,
        "refs": provision.refs,
        "note_refs": provision.note_refs,
        "table_data": provision.table,
        "page_start": provision.pages[0],
        "page_end": provision.pages[1],
        "source_file": provision.source_file,
        "source_version": provision.source_version,
    }


async def _upsert(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    for start in range(0, len(rows), _UPSERT_BATCH):
        batch = rows[start : start + _UPSERT_BATCH]
        statement = insert(CodeProvision).values(batch)
        await session.execute(
            statement.on_conflict_do_update(
                index_elements=[CodeProvision.market_code, CodeProvision.id],
                set_={
                    column: statement.excluded[column]
                    for column in batch[0]
                    if column not in ("market_code", "id")
                },
            )
        )


async def _prune(session: AsyncSession, market_code: str, title_number: str, keep: set[str]) -> int:
    existing = set(
        (
            await session.execute(
                select(CodeProvision.id).where(
                    CodeProvision.market_code == market_code,
                    CodeProvision.title_number == title_number,
                )
            )
        )
        .scalars()
        .all()
    )
    stale = existing - keep
    if not stale:
        return 0
    await session.execute(
        delete(CodeProvision).where(
            CodeProvision.market_code == market_code,
            CodeProvision.title_number == title_number,
            CodeProvision.id.in_(stale),
        )
    )
    return len(stale)


async def load_provisions(
    session: AsyncSession,
    directory: Path = DEFAULT_ARTIFACT_DIR,
    *,
    market_code: str = PHILADELPHIA_MARKET_CODE,
    title_numbers: list[str] | None = None,
) -> LoadReport:
    summary = read_qa_summary(directory)
    summarised = summary.title_numbers()
    expected = title_numbers if title_numbers is not None else summarised
    unknown = sorted(set(expected) - set(summarised))
    if unknown:
        raise ProvisionLoadError(
            f"{', '.join(unknown)} is not listed in {_SUMMARY_FILE}."
            if len(unknown) == 1
            else f"{', '.join(unknown)} are not listed in {_SUMMARY_FILE}."
        )

    qa_by_title = {title: read_title_qa(directory, title) for title in expected}
    for title_number, qa in qa_by_title.items():
        if qa.failing_gate() is None:
            _require_artifact(directory, title_number)

    results: list[TitleLoadResult] = []
    source_version: str | None = None
    for title_number in expected:
        failing = qa_by_title[title_number].failing_gate()
        if failing is not None:
            results.append(
                TitleLoadResult(
                    title_number=title_number,
                    loaded=False,
                    excluded_gate=failing.name,
                    excluded_value=failing.value,
                    excluded_detail=failing.detail,
                )
            )
            continue
        provisions = read_provisions(directory, title_number)
        rows = [_row(provision, title_number, market_code) for provision in provisions]
        if rows:
            await _upsert(session, rows)
            source_version = provisions[0].source_version
        pruned = await _prune(
            session, market_code, title_number, {provision.id for provision in provisions}
        )
        results.append(
            TitleLoadResult(
                title_number=title_number,
                loaded=True,
                provision_count=len(rows),
                pruned_count=pruned,
            )
        )

    await session.flush()

    if len(results) != len(expected):
        raise ProvisionLoadError(f"{len(results)} of {len(expected)} titles were accounted for.")

    report = LoadReport(
        source_version=source_version,
        market_code=market_code,
        titles_expected=len(expected),
        results=results,
    )
    logger.info(
        "phillycode_load",
        source_version=report.source_version,
        market_code=market_code,
        titles_expected=report.titles_expected,
        titles_loaded=report.loaded_titles,
        titles_excluded=report.excluded_titles,
        provisions=report.total_provisions,
    )
    return report
