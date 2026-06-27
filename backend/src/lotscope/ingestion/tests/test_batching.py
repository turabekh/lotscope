from lotscope.ingestion.upsert import batch_by_bind_limit, dedupe_on_conflict_key


def test_empty_rows_yield_nothing() -> None:
    assert list(batch_by_bind_limit([])) == []


def test_single_batch_when_under_limit() -> None:
    rows = [{"a": 1, "b": 2} for _ in range(10)]
    batches = list(batch_by_bind_limit(rows, max_params=100))
    assert len(batches) == 1
    assert len(batches[0]) == 10


def test_splits_to_keep_params_under_limit() -> None:
    rows = [{"a": 1, "b": 2, "c": 3, "d": 4, "e": 5} for _ in range(5000)]
    batches = list(batch_by_bind_limit(rows))
    assert all(len(batch) * 5 <= 30000 for batch in batches)
    assert sum(len(batch) for batch in batches) == 5000


def test_wide_rows_never_exceed_asyncpg_limit() -> None:
    rows = [dict.fromkeys((f"c{i}" for i in range(14)), 0) for _ in range(5000)]
    for batch in batch_by_bind_limit(rows):
        assert len(batch) * 14 < 32767


def test_dedupe_keeps_last_per_conflict_key() -> None:
    rows = [
        {"parcel_number": "1", "document_id": "D", "sale_price": 100},
        {"parcel_number": "1", "document_id": "D", "sale_price": 200},
        {"parcel_number": "2", "document_id": "D", "sale_price": 300},
    ]
    deduped = dedupe_on_conflict_key(rows, ["parcel_number", "document_id"])
    assert len(deduped) == 2
    by_key = {(r["parcel_number"], r["document_id"]): r["sale_price"] for r in deduped}
    assert by_key[("1", "D")] == 200
    assert by_key[("2", "D")] == 300
