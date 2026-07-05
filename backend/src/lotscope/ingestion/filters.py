import re

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

LI_DATE_COLUMNS = frozenset({"violationdate", "permitissuedate", "start_date"})


def _safe_date(value: str) -> str:
    if not _ISO_DATE.match(value):
        raise ValueError(f"invalid date literal: {value!r}")
    return value


def rtt_sales_where(min_sale_date: str) -> str:
    date = _safe_date(min_sale_date)
    return (
        f"document_type ILIKE '%DEED%' AND total_consideration > 0 AND recording_date >= '{date}'"
    )


def li_events_where(date_column: str, min_date: str) -> str:
    if date_column not in LI_DATE_COLUMNS:
        raise ValueError(f"unknown L&I date column: {date_column!r}")
    date = _safe_date(min_date)
    return f"{date_column} >= '{date}'"


ZBA_APPLICATION_TYPES = ("RB_ZBA", "Zoning Board of Adjustment")


def zba_appeals_where(min_decision_date: str) -> str:
    date = _safe_date(min_decision_date)
    types = ", ".join(f"'{value}'" for value in ZBA_APPLICATION_TYPES)
    return (
        f"applicationtype IN ({types}) AND (decisiondate >= '{date}' OR scheduleddate >= '{date}')"
    )
