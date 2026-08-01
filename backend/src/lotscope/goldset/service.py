from collections import Counter
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.goldset.logic import compare_case
from lotscope.goldset.schemas import EvaluationReport, GoldCase
from lotscope.verdict.composition import VERDICT_VERSION

_ACTUAL_SQL = text(
    "SELECT v.parcel_number, v.can_build_by_right, v.by_right_units, v.risk_flags, "
    "       p.resolved_zoning_code, p.base_zoning_code "
    "FROM parcel_verdict v JOIN parcel p ON p.parcel_number = v.parcel_number "
    "WHERE v.parcel_number = ANY(:parcel_numbers)"
)

_MASTER_PLAN_MARKER = "master plan"
_ACCESS_FLAG = "no_street_access"


def _actual_from_row(row: Any) -> dict[str, Any]:
    flags = row.risk_flags or []
    codes = [str(flag.get("code")) for flag in flags if isinstance(flag, dict)]
    return {
        "district_code": row.base_zoning_code or row.resolved_zoning_code,
        "can_build_by_right": row.can_build_by_right,
        "by_right_units": row.by_right_units,
        "requires_master_plan": any(_MASTER_PLAN_MARKER in code.lower() for code in codes),
        "street_access": _ACCESS_FLAG not in codes,
        "risk_flag_codes": codes,
    }


async def evaluate_gold_set(session: AsyncSession, cases: list[GoldCase]) -> EvaluationReport:
    parcel_numbers = [case.parcel_number for case in cases]
    rows = (await session.execute(_ACTUAL_SQL, {"parcel_numbers": parcel_numbers})).all()
    actual_by_parcel = {row.parcel_number: _actual_from_row(row) for row in rows}

    coverage: Counter[str] = Counter()
    for case in cases:
        for category in case.categories:
            coverage[category] += 1

    report = EvaluationReport(
        verdict_version=VERDICT_VERSION,
        total_cases=len(cases),
        evaluated=0,
        reviewed_cases=sum(1 for case in cases if case.review_status == "reviewed"),
        cases_without_expectations=sum(1 for case in cases if case.expected.is_empty()),
        category_coverage=dict(sorted(coverage.items())),
    )

    for case in cases:
        actual = actual_by_parcel.get(case.parcel_number)
        if actual is None:
            report.missing_verdict.append(case.parcel_number)
            continue
        report.evaluated += 1
        report.discrepancies.extend(compare_case(case.parcel_number, case.expected, actual))

    return report
