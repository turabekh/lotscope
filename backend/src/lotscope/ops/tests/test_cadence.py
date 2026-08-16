from datetime import UTC, date, datetime, timedelta

from lotscope.ops.cadence import (
    Cadence,
    FreshnessInput,
    cadence_for,
    evaluate_freshness,
)

_NOW = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)


def _row(status: str = "success", success_days_ago: int | None = 0) -> FreshnessInput:
    last = _NOW - timedelta(days=success_days_ago) if success_days_ago is not None else None
    return FreshnessInput(status=status, last_success_at=last, last_attempt_at=_NOW)


def test_daily_thresholds() -> None:
    assert evaluate_freshness(_row(success_days_ago=0), Cadence("daily"), _NOW).status == "green"
    assert evaluate_freshness(_row(success_days_ago=2), Cadence("daily"), _NOW).status == "amber"
    assert evaluate_freshness(_row(success_days_ago=3), Cadence("daily"), _NOW).status == "red"


def test_weekly_monthly_quarterly_thresholds() -> None:
    assert evaluate_freshness(_row(success_days_ago=5), Cadence("weekly"), _NOW).status == "green"
    assert evaluate_freshness(_row(success_days_ago=10), Cadence("weekly"), _NOW).status == "amber"
    assert evaluate_freshness(_row(success_days_ago=20), Cadence("weekly"), _NOW).status == "red"
    assert evaluate_freshness(_row(success_days_ago=40), Cadence("monthly"), _NOW).status == "amber"
    assert evaluate_freshness(_row(success_days_ago=70), Cadence("monthly"), _NOW).status == "red"
    assert (
        evaluate_freshness(_row(success_days_ago=100), Cadence("quarterly"), _NOW).status == "amber"
    )
    assert (
        evaluate_freshness(_row(success_days_ago=200), Cadence("quarterly"), _NOW).status == "red"
    )


def test_failed_last_run_is_red_regardless_of_age() -> None:
    verdict = evaluate_freshness(_row(status="failed", success_days_ago=0), Cadence("daily"), _NOW)
    assert verdict.status == "red"
    assert "failed" in verdict.reason.lower()


def test_never_loaded_is_red_for_expected_cadence() -> None:
    verdict = evaluate_freshness(_row(success_days_ago=None), Cadence("weekly"), _NOW)
    assert verdict.status == "red"
    assert "no successful load" in verdict.reason.lower()


def test_manual_is_never_red() -> None:
    fresh = evaluate_freshness(_row(success_days_ago=999), Cadence("manual"), _NOW)
    assert fresh.status == "green"
    assert "manual" in fresh.reason.lower()
    failed = evaluate_freshness(_row(status="failed", success_days_ago=1), Cadence("manual"), _NOW)
    assert failed.status == "green"
    never = evaluate_freshness(_row(success_days_ago=None), Cadence("manual"), _NOW)
    assert never.status == "amber"


def test_seasonal_off_season_is_green_with_note() -> None:
    cad = Cadence("seasonal", season_months=(8, 9))
    verdict = evaluate_freshness(_row(success_days_ago=None), cad, _NOW)
    assert verdict.status == "green"
    assert "next expected" in verdict.reason.lower()
    assert "August" in verdict.reason


def test_seasonal_in_season_awaiting_is_amber() -> None:
    cad = Cadence("seasonal", season_months=(8, 9))
    in_season = datetime(2026, 8, 20, tzinfo=UTC)
    row = FreshnessInput(status="success", last_success_at=None, last_attempt_at=in_season)
    verdict = evaluate_freshness(row, cad, in_season)
    assert verdict.status == "amber"
    assert "2026" in verdict.reason


def test_seasonal_in_season_loaded_is_green() -> None:
    cad = Cadence("seasonal", season_months=(8, 9))
    in_season = datetime(2026, 9, 5, tzinfo=UTC)
    row = FreshnessInput(
        status="success",
        last_success_at=datetime(2026, 8, 30, tzinfo=UTC),
        last_attempt_at=in_season,
    )
    verdict = evaluate_freshness(row, cad, in_season)
    assert verdict.status == "green"


def test_seasonal_in_season_failed_is_red() -> None:
    cad = Cadence("seasonal", season_months=(8, 9))
    in_season = datetime(2026, 8, 20, tzinfo=UTC)
    row = FreshnessInput(status="failed", last_success_at=None, last_attempt_at=in_season)
    assert evaluate_freshness(row, cad, in_season).status == "red"


def test_cadence_map_covers_the_seasonal_tax_claim() -> None:
    cad = cadence_for("hbg", "dc_tax_claim")
    assert cad.kind == "seasonal"
    assert cad.season_months == (8, 9)


def test_unknown_dataset_falls_back_to_default_monthly() -> None:
    assert cadence_for("phl", "not_a_dataset").kind == "monthly"


def test_no_source_marked_green_by_accident() -> None:
    for cadence in (Cadence("daily"), Cadence("weekly"), Cadence("monthly"), Cadence("quarterly")):
        verdict = evaluate_freshness(_row(success_days_ago=None), cadence, _NOW)
        assert verdict.status != "green"


def test_a_freshly_fetched_source_is_still_stale_when_its_data_is_four_years_old() -> None:
    verdict = evaluate_freshness(
        FreshnessInput(
            status="success",
            last_success_at=_NOW,
            last_attempt_at=_NOW,
            data_vintage=date(2022, 6, 1),
        ),
        Cadence("daily"),
        _NOW,
    )

    assert verdict.status == "red"
    assert "data as of 2022-06-01" in verdict.reason


def test_the_worse_of_fetch_and_vintage_wins_when_the_fetch_is_the_problem() -> None:
    verdict = evaluate_freshness(
        FreshnessInput(
            status="success",
            last_success_at=_NOW - timedelta(days=40),
            last_attempt_at=_NOW,
            data_vintage=_NOW.date(),
        ),
        Cadence("daily"),
        _NOW,
    )

    assert verdict.status == "red"
    assert "last success" in verdict.reason
    assert verdict.vintage_reason is not None


def test_a_current_source_with_current_data_stays_green() -> None:
    verdict = evaluate_freshness(
        FreshnessInput(
            status="success",
            last_success_at=_NOW,
            last_attempt_at=_NOW,
            data_vintage=_NOW.date(),
        ),
        Cadence("daily"),
        _NOW,
    )

    assert verdict.status == "green"


def test_an_unknown_vintage_leaves_the_fetch_verdict_alone() -> None:
    verdict = evaluate_freshness(
        FreshnessInput(
            status="success", last_success_at=_NOW, last_attempt_at=_NOW, data_vintage=None
        ),
        Cadence("daily"),
        _NOW,
    )

    assert verdict.status == "green"
    assert verdict.vintage_reason is None
