from typing import Any

from lotscope.goldset.schemas import CRITICAL_FIELDS, Discrepancy, ExpectedFacts, Severity


def _severity(field_name: str) -> Severity:
    return "critical" if field_name in CRITICAL_FIELDS else "material"


def _render(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def compare_case(
    parcel_number: str, expected: ExpectedFacts, actual: dict[str, Any]
) -> list[Discrepancy]:
    discrepancies: list[Discrepancy] = []

    for field_name in ("district_code", "can_build_by_right", "by_right_units", "street_access"):
        want = getattr(expected, field_name)
        if want is None:
            continue
        got = actual.get(field_name)
        if got != want:
            discrepancies.append(
                Discrepancy(
                    parcel_number=parcel_number,
                    field_name=field_name,
                    expected=_render(want),
                    actual=_render(got),
                    severity=_severity(field_name),
                )
            )

    if expected.requires_master_plan is True and actual.get("requires_master_plan") is not True:
        discrepancies.append(
            Discrepancy(
                parcel_number=parcel_number,
                field_name="requires_master_plan",
                expected="True",
                actual=_render(actual.get("requires_master_plan")),
                severity="critical",
            )
        )

    actual_flags = {str(code) for code in actual.get("risk_flag_codes", [])}
    for code in expected.expected_risk_flags:
        if code not in actual_flags:
            discrepancies.append(
                Discrepancy(
                    parcel_number=parcel_number,
                    field_name=f"risk_flag:{code}",
                    expected="present",
                    actual="absent",
                    severity="material",
                )
            )

    return discrepancies
