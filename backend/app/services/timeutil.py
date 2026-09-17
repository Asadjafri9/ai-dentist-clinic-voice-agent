"""Timezone helpers. All stored timestamps are UTC instants; local-date
scheduling happens only through timezone-aware code here."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

UTC = UTC


def now_utc() -> datetime:
    return datetime.now(UTC)


def tz(name: str) -> ZoneInfo:
    return ZoneInfo(name)


def utc_to_local(dt: datetime, tzname: str) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(tz(tzname))


def local_to_utc(d: date, hhmm: str, tzname: str) -> datetime:
    """Convert a local date + 'HH:MM' wall time to a UTC instant.

    Nonexistent local times (spring-forward) are shifted forward by the
    gap; ambiguous times (fall-back) resolve to the earlier instant.
    """
    h, m = int(hhmm[:2]), int(hhmm[3:])
    naive = datetime.combine(d, time(h, m))
    z = tz(tzname)
    aware = naive.replace(tzinfo=z)
    # Detect nonexistent wall times: round-trip check.
    back = aware.astimezone(UTC).astimezone(z)
    if back.replace(tzinfo=None) != naive:
        aware = (naive + timedelta(hours=1)).replace(tzinfo=z)
    return aware.astimezone(UTC)


def local_date_of(dt: datetime, tzname: str) -> date:
    return utc_to_local(dt, tzname).date()


def parse_local_date(s: str) -> date:
    return date.fromisoformat(s)


def fmt_local(dt: datetime, tzname: str) -> str:
    """Human label like 'Friday, September 18 at 3:30 PM'."""
    local = utc_to_local(dt, tzname)
    return local.strftime("%A, %B %-d at %-I:%M %p")


def fmt_date(d: date) -> str:
    return d.strftime("%A, %B %-d")
