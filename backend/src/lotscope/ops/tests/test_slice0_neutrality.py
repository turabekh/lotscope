import inspect

from lotscope.distress import scoring as distress_scoring
from lotscope.distress import service as distress_service
from lotscope.risk import scoring as risk_scoring
from lotscope.risk import service as risk_service
from lotscope.valuation import service as valuation_service
from lotscope.verdict import composition, decision

_NEW_COLUMNS = ("delinquency_owner", "snapshot_period", "case_status")

_SCORING_SOURCES = (
    distress_scoring,
    distress_service,
    risk_scoring,
    risk_service,
    valuation_service,
    composition,
    decision,
)


def test_no_scoring_path_reads_the_columns_slice_zero_added() -> None:
    offenders: list[str] = []
    for module in _SCORING_SOURCES:
        source = inspect.getsource(module)
        for column in _NEW_COLUMNS:
            if column in source:
                offenders.append(f"{module.__name__} reads {column}")

    assert offenders == []


def test_the_delinquency_flag_still_ignores_who_owes_it() -> None:
    assert list(risk_scoring.TaxSignal.__dataclass_fields__) == [
        "is_delinquent",
        "total_due",
        "years_owed",
        "in_sheriff_sale",
    ]
