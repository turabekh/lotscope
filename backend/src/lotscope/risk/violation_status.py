OPEN_VIOLATION_STATUS = "OPEN"

CLOSED_CASE_STATUSES: frozenset[str] = frozenset({"CLOSED"})


def is_open_violation(status: str | None, case_status: str | None) -> bool:
    if (status or "").strip().upper() != OPEN_VIOLATION_STATUS:
        return False
    return (case_status or "").strip().upper() not in CLOSED_CASE_STATUSES


def open_violation_sql(alias: str) -> str:
    closed = ", ".join(f"'{value}'" for value in sorted(CLOSED_CASE_STATUSES))
    return (
        f"upper(coalesce({alias}.status, '')) = '{OPEN_VIOLATION_STATUS}' "
        f"AND upper(coalesce({alias}.case_status, '')) NOT IN ({closed})"
    )
