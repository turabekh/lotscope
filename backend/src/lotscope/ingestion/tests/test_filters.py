import pytest

from lotscope.ingestion.filters import (
    LI_DATE_COLUMNS,
    li_events_where,
    rtt_sales_where,
)


def test_rtt_sales_where_bounds_to_recent_real_deeds() -> None:
    clause = rtt_sales_where("2021-01-01")
    assert "document_type ILIKE '%DEED%'" in clause
    assert "total_consideration > 0" in clause
    assert "recording_date >= '2021-01-01'" in clause


def test_rtt_sales_where_rejects_malformed_date() -> None:
    with pytest.raises(ValueError, match="date"):
        rtt_sales_where("2021/01/01")


def test_rtt_sales_where_rejects_injection_attempt() -> None:
    with pytest.raises(ValueError, match="date"):
        rtt_sales_where("2021-01-01'; DROP TABLE rtt_summary;--")


@pytest.mark.parametrize("column", sorted(LI_DATE_COLUMNS))
def test_li_events_where_allows_known_columns(column: str) -> None:
    clause = li_events_where(column, "2023-01-01")
    assert clause == f"{column} >= '2023-01-01'"


def test_li_events_where_rejects_unknown_column() -> None:
    with pytest.raises(ValueError, match="column"):
        li_events_where("dropped_at", "2023-01-01")


def test_li_events_where_rejects_malformed_date() -> None:
    with pytest.raises(ValueError, match="date"):
        li_events_where("violationdate", "not-a-date")
