import json
import shutil
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.provisions.loader import ProvisionLoadError, load_provisions
from lotscope.provisions.models import CodeProvision

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def artifacts(tmp_path: Path) -> Path:
    target = tmp_path / "phillycode"
    shutil.copytree(FIXTURES, target)
    return target


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in records))


def _fail_toc_gate(artifacts: Path, title_number: str) -> None:
    path = artifacts / f"qa_title_{title_number}.json"
    qa = json.loads(path.read_text())
    for gate in qa["gates"]:
        if gate["name"] == "1_toc_reconciliation":
            gate["passed"] = False
            gate["value"] = "1 sections emitted, 2 listed in the title's TOC"
            gate["detail"] = "missing=['7-102'] extra=[] duplicates=[]."
    qa["passed"] = False
    path.write_text(json.dumps(qa))


async def _get(session: AsyncSession, provision_id: str) -> CodeProvision:
    row = await session.get(CodeProvision, {"market_code": "phl", "id": provision_id})
    assert row is not None
    return row


async def _rows(session: AsyncSession, title_number: str | None = None) -> list[CodeProvision]:
    statement = select(CodeProvision).order_by(CodeProvision.title_number, CodeProvision.ordinal)
    if title_number is not None:
        statement = statement.where(CodeProvision.title_number == title_number)
    return list((await session.execute(statement)).scalars())


async def test_a_passing_artifact_set_loads_every_title(
    db_session: AsyncSession, artifacts: Path
) -> None:
    report = await load_provisions(db_session, artifacts)

    assert report.loaded_titles == ["7", "8.1"]
    assert report.excluded_titles == []
    assert report.total_provisions == 10
    assert report.source_version == "May 25, 2026"
    assert {result.title_number: result.provision_count for result in report.results} == {
        "7": 8,
        "8.1": 2,
    }


async def test_the_loader_maps_the_parser_shape_onto_the_canonical_columns(
    db_session: AsyncSession, artifacts: Path
) -> None:
    await load_provisions(db_session, artifacts)

    table_node = await _get(db_session, "7-102#table1")
    assert table_node.market_code == "phl"
    assert table_node.title_number == "7"
    assert table_node.ordinal == 8
    assert table_node.page_start == 11
    assert table_node.page_end == 11
    assert table_node.table_data is not None
    assert table_node.table_data["caption"] == "Table 7-102-1: Fixture Values"
    assert table_node.source_file == "philadelphiahomerulecharter.pdf"
    assert table_node.source_version == "May 25, 2026"

    subsection = await _get(db_session, "7-101(1)")
    assert subsection.refs == ["7-102"]
    assert subsection.parent == "7-101"
    assert subsection.path == ["7", "7-100", "7-101", "(1)"]
    assert subsection.table_data is None


async def test_a_provision_without_a_table_stores_sql_null_not_json_null(
    db_session: AsyncSession, artifacts: Path
) -> None:
    await load_provisions(db_session, artifacts)

    with_table = await db_session.scalar(
        select(func.count()).select_from(CodeProvision).where(CodeProvision.table_data.is_not(None))
    )
    assert with_table == 1


async def test_a_title_failing_a_gate_loads_nothing_and_is_named_in_the_report(
    db_session: AsyncSession, artifacts: Path
) -> None:
    _fail_toc_gate(artifacts, "7")

    report = await load_provisions(db_session, artifacts)

    assert report.loaded_titles == ["8.1"]
    assert report.excluded_titles == ["7"]
    excluded = next(result for result in report.results if result.title_number == "7")
    assert excluded.excluded_gate == "1_toc_reconciliation"
    assert excluded.excluded_value == "1 sections emitted, 2 listed in the title's TOC"
    assert excluded.excluded_detail == "missing=['7-102'] extra=[] duplicates=[]."
    assert await _rows(db_session, "7") == []
    assert len(await _rows(db_session, "8.1")) == 2


async def test_one_malformed_record_fails_its_whole_title_and_spares_the_sibling(
    db_session: AsyncSession, artifacts: Path
) -> None:
    path = artifacts / "title_7.jsonl"
    records = _read_jsonl(path)
    del records[3]["order"]
    _write_jsonl(path, records)

    with pytest.raises(ProvisionLoadError) as error:
        await load_provisions(db_session, artifacts)

    assert "title_7.jsonl" in str(error.value)
    assert await _rows(db_session, "7") == []


async def test_a_qa_file_in_the_summary_shape_raises_before_anything_loads(
    db_session: AsyncSession, artifacts: Path
) -> None:
    summary = json.loads((artifacts / "qa_summary.json").read_text())
    (artifacts / "qa_title_7.json").write_text(json.dumps(summary["titles"][0]))

    with pytest.raises(ProvisionLoadError) as error:
        await load_provisions(db_session, artifacts)

    assert "qa_title_7.json" in str(error.value)
    assert await _rows(db_session) == []


async def test_loading_twice_leaves_the_same_rows(
    db_session: AsyncSession, artifacts: Path
) -> None:
    await load_provisions(db_session, artifacts)
    first = [
        (row.id, row.cite, row.ordinal, row.text, row.title_number)
        for row in await _rows(db_session)
    ]

    report = await load_provisions(db_session, artifacts)
    second = [
        (row.id, row.cite, row.ordinal, row.text, row.title_number)
        for row in await _rows(db_session)
    ]

    assert first == second
    assert report.total_provisions == 10
    assert await db_session.scalar(select(func.count()).select_from(CodeProvision)) == 10


async def test_a_record_dropped_from_the_artifact_is_pruned_from_its_title_alone(
    db_session: AsyncSession, artifacts: Path
) -> None:
    await load_provisions(db_session, artifacts)
    path = artifacts / "title_7.jsonl"
    records = [record for record in _read_jsonl(path) if record["id"] != "7-101(2)"]
    _write_jsonl(path, records)

    report = await load_provisions(db_session, artifacts)

    assert {row.id for row in await _rows(db_session, "7")} == {
        "7",
        "7-100",
        "7-101",
        "7-101(1)",
        "7-101~2",
        "7-102",
        "7-102#table1",
    }
    assert len(await _rows(db_session, "8.1")) == 2
    pruned = next(result for result in report.results if result.title_number == "7")
    assert pruned.pruned_count == 1


async def test_a_title_number_that_disagrees_with_the_records_fails_the_title(
    db_session: AsyncSession, artifacts: Path
) -> None:
    path = artifacts / "title_7.jsonl"
    records = _read_jsonl(path)
    records[4]["path"] = ["9", "7-100", "7-101", "(2)"]
    _write_jsonl(path, records)

    with pytest.raises(ProvisionLoadError) as error:
        await load_provisions(db_session, artifacts)

    assert "7-101(2)" in str(error.value)
    assert await _rows(db_session, "7") == []


async def test_an_artifact_file_missing_for_a_summarised_title_fails_the_run(
    db_session: AsyncSession, artifacts: Path
) -> None:
    (artifacts / "title_8.1.jsonl").unlink()

    with pytest.raises(ProvisionLoadError) as error:
        await load_provisions(db_session, artifacts)

    assert "title_8.1.jsonl" in str(error.value)
    assert await _rows(db_session) == []


async def test_a_single_title_can_be_loaded_without_disturbing_the_others(
    db_session: AsyncSession, artifacts: Path
) -> None:
    await load_provisions(db_session, artifacts)

    report = await load_provisions(db_session, artifacts, title_numbers=["8.1"])

    assert report.loaded_titles == ["8.1"]
    assert report.titles_expected == 1
    assert len(await _rows(db_session, "7")) == 8
