from lotscope.vacancy.scoring import (
    VPI_BASELINE,
    VacancySignals,
    has_substantial_structure,
    vacancy_confidence,
)


def _signals(**overrides: object) -> VacancySignals:
    base: dict[str, object] = {
        "is_vacant": True,
        "vacancy_violations": 0,
        "demolitions": 0,
        "recent_permits": 0,
        "improvement_value": None,
        "land_value": None,
    }
    base.update(overrides)
    return VacancySignals(**base)  # type: ignore[arg-type]


def test_non_vacant_parcel_has_no_confidence() -> None:
    assert vacancy_confidence(_signals(is_vacant=False)) is None


def test_bare_vpi_flag_sits_at_baseline() -> None:
    assert vacancy_confidence(_signals()) == VPI_BASELINE


def test_corroborating_signals_raise_confidence() -> None:
    raised = vacancy_confidence(_signals(vacancy_violations=2, demolitions=1))
    assert raised is not None
    assert raised > VPI_BASELINE


def test_recent_permit_lowers_confidence() -> None:
    lowered = vacancy_confidence(_signals(recent_permits=1))
    assert lowered is not None
    assert lowered < VPI_BASELINE


def test_substantial_structure_lowers_confidence() -> None:
    lowered = vacancy_confidence(_signals(improvement_value=200_000, land_value=50_000))
    assert lowered is not None
    assert lowered < VPI_BASELINE


def test_confidence_is_clamped_to_unit_interval() -> None:
    floored = vacancy_confidence(
        _signals(recent_permits=1, improvement_value=500_000, land_value=1_000)
    )
    assert floored == 0.0
    capped = vacancy_confidence(_signals(vacancy_violations=5, demolitions=5))
    assert capped is not None
    assert capped <= 1.0


def test_substantial_structure_requires_ratio_and_floor() -> None:
    assert has_substantial_structure(200_000, 50_000) is True
    assert has_substantial_structure(10_000, 0) is False
    assert has_substantial_structure(60_000, 40_000) is False
    assert has_substantial_structure(None, 10_000) is False
