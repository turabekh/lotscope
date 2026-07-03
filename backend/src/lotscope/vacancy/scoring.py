from dataclasses import dataclass

VPI_BASELINE = 0.6
LOW_CONFIDENCE_THRESHOLD = 0.5

_VACANCY_VIOLATION_BOOST = 0.2
_DEMOLITION_BOOST = 0.15
_RECENT_PERMIT_PENALTY = 0.35
_STRUCTURE_PENALTY = 0.4
_STRUCTURE_MIN_IMPROVEMENT = 25_000.0
_STRUCTURE_VALUE_RATIO = 2.0


@dataclass(frozen=True)
class VacancySignals:
    is_vacant: bool
    vacancy_violations: int
    demolitions: int
    recent_permits: int
    improvement_value: float | None
    land_value: float | None


def has_substantial_structure(improvement_value: float | None, land_value: float | None) -> bool:
    if improvement_value is None or improvement_value < _STRUCTURE_MIN_IMPROVEMENT:
        return False
    return improvement_value >= _STRUCTURE_VALUE_RATIO * (land_value or 0.0)


def vacancy_confidence(signals: VacancySignals) -> float | None:
    if not signals.is_vacant:
        return None
    score = VPI_BASELINE
    if signals.vacancy_violations > 0:
        score += _VACANCY_VIOLATION_BOOST
    if signals.demolitions > 0:
        score += _DEMOLITION_BOOST
    if signals.recent_permits > 0:
        score -= _RECENT_PERMIT_PENALTY
    if has_substantial_structure(signals.improvement_value, signals.land_value):
        score -= _STRUCTURE_PENALTY
    return round(min(1.0, max(0.0, score)), 4)
