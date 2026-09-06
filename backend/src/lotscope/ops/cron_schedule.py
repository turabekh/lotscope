"""The cron timetable, written once, read by the worker and by readiness.

The worker schedules these and `/health/ready` decides from the same list whether one
has stopped running. Kept as data with no function references so both sides can import
it, and a test fails if they ever disagree — a stale-job check against a timetable the
worker does not actually run would report on jobs that do not exist and stay silent
about the ones that do.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Literal

# Spelled as arq spells them, so the timetable can be handed to `cron()` unchanged.
Weekday = Literal["mon", "tues", "wed", "thurs", "fri", "sat", "sun"]

_WEEKDAYS: dict[Weekday, int] = {
    "mon": 0,
    "tues": 1,
    "wed": 2,
    "thurs": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}
_EVERY_HOUR = tuple(range(24))
_SEARCH_DAYS = 30


@dataclass(frozen=True)
class CronSpec:
    """When one job is due. `hours=None` means every hour."""

    name: str
    hours: tuple[int, ...] | None
    minutes: tuple[int, ...] = (0,)
    weekday: Weekday | None = None

    @property
    def slots(self) -> list[tuple[int, int]]:
        hours = _EVERY_HOUR if self.hours is None else self.hours
        return sorted(((h, m) for h in hours for m in self.minutes), reverse=True)

    def runs_on_weekday(self, moment: datetime) -> bool:
        return self.weekday is None or moment.weekday() == _WEEKDAYS[self.weekday]


CRON_SCHEDULE: tuple[CronSpec, ...] = (
    CronSpec("send_error_digest_email", None, minutes=(0, 15, 30, 45)),
    CronSpec("sweep_ingestion_retention", (2,)),
    CronSpec("summarise_conversations", (3,), minutes=(30,)),
    CronSpec("ingest_all", (4,)),
    CronSpec("send_ops_alerts", (5,), minutes=(30,)),
    CronSpec("send_sheriff_change_emails", (5,), minutes=(45,)),
    CronSpec("build_daily_signals", (6,), minutes=(15,)),
    CronSpec("recompute_vacancy_confidence", (6,), minutes=(30,)),
    CronSpec("rebuild_screen_index", (7,)),
    CronSpec("recompute_distress", (8,)),
    CronSpec("send_sales_week_emails", (8,), weekday="mon"),
    CronSpec("recompute_assemblage", (8,), minutes=(30,)),
    CronSpec("recompute_buyers", (9,)),
    CronSpec("snapshot_stats", (9,), minutes=(30,)),
    CronSpec("send_ops_health_digest", (10,)),
    CronSpec("reconcile_upstream_sample", (11,)),
    CronSpec("send_morning_briefs", (11, 12)),
    CronSpec("send_daily_packet_emails", (13, 14)),
    CronSpec("send_daily_digests", (13,)),
    CronSpec("send_weekly_digests", (13,), minutes=(30,), weekday="mon"),
    CronSpec("send_deal_reminder_emails", (13,), minutes=(45,)),
)

SCHEDULED_NAMES = frozenset(spec.name for spec in CRON_SCHEDULE)


def previous_fires(spec: CronSpec, now: datetime, count: int = 2) -> list[datetime]:
    """The last `count` times this job was due, most recent first."""
    moment = now.astimezone(UTC).replace(second=0, microsecond=0)
    slots = spec.slots
    found: list[datetime] = []
    day = moment.date()
    for _ in range(_SEARCH_DAYS):
        for hour, minute in slots:
            candidate = datetime.combine(day, time(hour, minute), tzinfo=UTC)
            if candidate <= moment and spec.runs_on_weekday(candidate):
                found.append(candidate)
                if len(found) == count:
                    return found
        day -= timedelta(days=1)
    return found


def missed_since(spec: CronSpec, now: datetime) -> datetime | None:
    """The moment a job must have succeeded since, to not count as stale.

    Two scheduled runs back, so one missed night is not an alarm and two are. A job that
    has not yet been due twice cannot be judged, and returns None.
    """
    fires = previous_fires(spec, now, count=2)
    return fires[1] if len(fires) == 2 else None
