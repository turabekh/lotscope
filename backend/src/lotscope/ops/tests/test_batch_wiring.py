import inspect

from lotscope.distress import scoring as distress_scoring
from lotscope.distress import service as distress_service
from lotscope.distress.profiles import profile_for_market
from lotscope.risk import scoring as risk_scoring
from lotscope.risk import service as risk_service
from lotscope.valuation import service as valuation_service
from lotscope.verdict import composition, decision

_ATTRIBUTION_COLUMNS = ("delinquency_owner", "snapshot_period")
_VIOLATION_COLUMN = "case_status"

_UNTOUCHED_BY_THIS_BATCH = (valuation_service, composition, decision)


def test_the_delinquency_columns_now_reach_the_paths_that_needed_them() -> None:
    risk_source = inspect.getsource(risk_service)
    distress_source = inspect.getsource(distress_service)

    for column in _ATTRIBUTION_COLUMNS:
        assert column in risk_source, f"risk service no longer reads {column}"
        assert column in distress_source, f"distress service no longer reads {column}"


def test_the_open_violation_rule_reads_the_case_status_column() -> None:
    from lotscope.risk import violation_status

    assert _VIOLATION_COLUMN in inspect.getsource(violation_status)


def test_the_delinquency_flag_now_knows_who_owes_it() -> None:
    assert "attribution" in risk_scoring.TaxSignal.__dataclass_fields__


def test_distress_separates_open_violations_from_violations_on_record() -> None:
    fields = distress_scoring.DistressSignals.__dataclass_fields__

    assert "open_violations" in fields
    assert "violations_on_record" in fields
    assert "violations" not in fields


def test_philadelphia_scores_under_the_second_profile_version() -> None:
    assert profile_for_market("phl").profile_id == "philly-distress-v2"


def test_valuation_and_verdict_composition_stayed_out_of_this_batch() -> None:
    offenders: list[str] = []
    for module in _UNTOUCHED_BY_THIS_BATCH:
        source = inspect.getsource(module)
        for column in (*_ATTRIBUTION_COLUMNS, _VIOLATION_COLUMN):
            if column in source:
                offenders.append(f"{module.__name__} reads {column}")

    assert offenders == []
