from datetime import date, timedelta

from lotscope.ingestion.vintage import vintage_from_dates, vintage_from_year_month


def test_the_latest_period_becomes_the_vintage() -> None:
    assert vintage_from_year_month(["202105", "202206", "202201"]) == date(2022, 6, 1)


def test_a_frozen_snapshot_reports_its_single_period() -> None:
    assert vintage_from_year_month(["202206"] * 50) == date(2022, 6, 1)


def test_unparseable_periods_yield_no_vintage_rather_than_a_wrong_one() -> None:
    assert vintage_from_year_month([None, "", "2022", "20220601", "abcdef"]) is None
    assert vintage_from_year_month(["202213"]) is None


def test_the_latest_recorded_date_becomes_the_vintage() -> None:
    values = [date(2024, 1, 1), date(2026, 8, 1), date(2025, 5, 5)]

    assert vintage_from_dates(values) == date(2026, 8, 1)


def test_a_future_dated_row_cannot_pass_as_the_vintage() -> None:
    tomorrow = date.today() + timedelta(days=1)

    assert vintage_from_dates([date(2026, 8, 1), tomorrow]) == date(2026, 8, 1)


def test_no_usable_dates_yield_no_vintage() -> None:
    assert vintage_from_dates([]) is None
    assert vintage_from_dates([None]) is None
    assert vintage_from_dates([date.today() + timedelta(days=10)]) is None
