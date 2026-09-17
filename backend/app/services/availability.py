"""Availability engine.

Provider availability is stored as recurring windows plus exceptions.
Candidate intervals are generated per service duration and checked
against confirmed appointments with buffers — never modeled as
independently bookable fixed blocks.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from app.services import timeutil
from app.services.timeutil import local_to_utc, now_utc, utc_to_local

WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

TIME_WINDOWS = {
    "morning": (6, 12),
    "afternoon": (12, 17),
    "evening": (17, 22),
    "any": (0, 24),
}


@dataclass(frozen=True)
class Window:
    """A UTC interval during which a provider may take appointments."""

    start: datetime
    end: datetime


@dataclass(frozen=True)
class SlotCandidate:
    provider_id: str
    provider_name: str
    start_at: datetime
    end_at: datetime


def business_hours_window(
    business: dict[str, Any], local_date: date
) -> tuple[str, str] | None:
    """Return ('HH:MM','HH:MM') clinic hours for the local date, or None."""
    hours = business.get("business_hours") or {}
    key = WEEKDAY_KEYS[local_date.weekday()]
    day = hours.get(key) or {}
    if day.get("closed"):
        return None
    open_t, close_t = day.get("open"), day.get("close")
    if not open_t or not close_t or open_t >= close_t:
        return None
    return open_t, close_t


def _rule_window_for_date(
    rule: dict[str, Any], local_date: date
) -> tuple[str, str] | None:
    if not rule.get("active", True):
        return None
    if rule.get("weekday") != local_date.weekday():
        return None
    eff_from = rule.get("effective_from")
    eff_to = rule.get("effective_to")
    iso = local_date.isoformat()
    if eff_from and iso < eff_from:
        return None
    if eff_to and iso > eff_to:
        return None
    s, e = rule.get("start_local"), rule.get("end_local")
    if not s or not e or s >= e:
        return None
    return s, e


def _clip(a: tuple[str, str], b: tuple[str, str]) -> tuple[str, str] | None:
    start, end = max(a[0], b[0]), min(a[1], b[1])
    return (start, end) if start < end else None


def effective_local_windows(
    *,
    business: dict[str, Any],
    rules: Iterable[dict[str, Any]],
    exceptions: Iterable[dict[str, Any]],
    local_date: date,
) -> list[tuple[str, str]]:
    """Effective provider windows on a local date, as (start,end) 'HH:MM'.

    Provider rules are clipped to clinic business hours, then exceptions
    apply: 'closed' removes overlap (or the whole day), 'added' appends.
    """
    clinic = business_hours_window(business, local_date)
    windows: list[tuple[str, str]] = []
    if clinic is not None:
        for rule in rules:
            rw = _rule_window_for_date(rule, local_date)
            if rw is None:
                continue
            clipped = _clip(rw, clinic)
            if clipped:
                windows.append(clipped)

    closed_all = False
    for exc in exceptions:
        if not exc.get("active", True):
            continue
        if exc.get("local_date") != local_date.isoformat():
            continue
        kind = exc.get("kind", "closed")
        s, e = exc.get("start_local"), exc.get("end_local")
        if kind == "closed":
            if not s or not e:
                closed_all = True
            else:
                windows = _subtract_local(windows, (s, e))
        elif kind == "added" and s and e and s < e and clinic is not None:
            clipped = _clip((s, e), clinic)
            if clipped:
                windows.append(clipped)
    if closed_all:
        return []
    return _merge_local(windows)


def _subtract_local(
    windows: list[tuple[str, str]], cut: tuple[str, str]
) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for s, e in windows:
        if cut[1] <= s or cut[0] >= e:
            out.append((s, e))
            continue
        if cut[0] > s:
            out.append((s, min(cut[0], e)))
        if cut[1] < e:
            out.append((max(cut[1], s), e))
    return out


def _merge_local(windows: list[tuple[str, str]]) -> list[tuple[str, str]]:
    if not windows:
        return []
    ws = sorted(windows)
    merged = [ws[0]]
    for s, e in ws[1:]:
        ls, le = merged[-1]
        if s <= le:
            merged[-1] = (ls, max(le, e))
        else:
            merged.append((s, e))
    return merged


def windows_to_utc(
    windows: Iterable[tuple[str, str]], local_date: date, tzname: str
) -> list[Window]:
    out: list[Window] = []
    for s, e in windows:
        start = local_to_utc(local_date, s, tzname)
        end = local_to_utc(local_date, e, tzname)
        if end > start:
            out.append(Window(start, end))
    return out


def in_time_window(local_dt: datetime, window: str) -> bool:
    lo, hi = TIME_WINDOWS.get(window, (0, 24))
    return lo <= local_dt.hour < hi


def generate_candidates(
    *,
    business: dict[str, Any],
    service: dict[str, Any],
    providers: list[dict[str, Any]],
    rules_by_provider: dict[str, list[dict[str, Any]]],
    exceptions_by_provider: dict[str, list[dict[str, Any]]],
    appointments_by_provider: dict[str, list[dict[str, Any]]],
    local_date: date,
    time_window: str = "any",
    now: datetime | None = None,
    limit: int = 5,
) -> list[SlotCandidate]:
    """Generate valid start times on one local date across providers.

    Candidates are aligned to the clinic's slot increment, must fit
    fully inside an effective availability window, cannot overlap any
    confirmed appointment expanded by this service's buffers, must be
    in the future beyond the lead time, and respect the booking
    horizon. Results are sorted by start time.
    """
    now = now or now_utc()
    tzname = business["timezone"]
    increment = int(business.get("slot_increment_minutes") or 30)
    lead = timedelta(minutes=int(business.get("booking_lead_time_minutes") or 0))
    duration = timedelta(minutes=int(service["duration_minutes"]))
    buf_before = timedelta(minutes=int(service.get("buffer_before_minutes") or 0))
    buf_after = timedelta(minutes=int(service.get("buffer_after_minutes") or 0))
    horizon = date.fromisoformat(
        utc_to_local(now + timedelta(days=int(business.get("booking_horizon_days", 90))), tzname)
        .date()
        .isoformat()
    )
    if local_date > horizon or local_date < utc_to_local(now, tzname).date():
        return []

    out: list[SlotCandidate] = []
    for provider in providers:
        pid = provider["_id"]
        local_windows = effective_local_windows(
            business=business,
            rules=rules_by_provider.get(pid, []),
            exceptions=exceptions_by_provider.get(pid, []),
            local_date=local_date,
        )
        utc_windows = windows_to_utc(local_windows, local_date, tzname)
        if not utc_windows:
            continue

        busy = [
            (a["start_at"], a["end_at"])
            for a in appointments_by_provider.get(pid, [])
            if a.get("status") == "confirmed"
        ]

        for w in utc_windows:
            # Align starts to the increment grid in local time.
            local_day_start = datetime.combine(local_date, datetime.min.time()).replace(
                tzinfo=timeutil.tz(tzname)
            )
            first_offset = int(
                (w.start - local_day_start.astimezone(timeutil.UTC)).total_seconds()
                // 60
            )
            grid_minutes = ((first_offset + increment - 1) // increment) * increment
            start = local_day_start.astimezone(timeutil.UTC) + timedelta(
                minutes=grid_minutes
            )
            while start + duration <= w.end:
                end = start + duration
                local_start = utc_to_local(start, tzname)
                if (
                    start >= now + lead
                    and in_time_window(local_start, time_window)
                    and not _blocked(start, end, busy, buf_before, buf_after)
                ):
                    out.append(
                        SlotCandidate(
                            provider_id=pid,
                            provider_name=provider.get("name", "Provider"),
                            start_at=start,
                            end_at=end,
                        )
                    )
                start += timedelta(minutes=increment)
        if len(out) >= limit * 3:
            break

    out.sort(key=lambda c: (c.start_at, c.provider_name))
    return out[:limit]


def _blocked(
    start: datetime,
    end: datetime,
    busy: list[tuple[datetime, datetime]],
    buf_before: timedelta,
    buf_after: timedelta,
) -> bool:
    cand_start, cand_end = start - buf_before, end + buf_after
    for bs, be in busy:
        if bs < cand_end and be > cand_start:
            return True
    return False


def interval_fits_schedule(
    *,
    business: dict[str, Any],
    service: dict[str, Any],
    provider_id: str,
    rules: list[dict[str, Any]],
    exceptions: list[dict[str, Any]],
    appointments: list[dict[str, Any]],
    start_at: datetime,
    end_at: datetime,
    now: datetime | None = None,
) -> bool:
    """Revalidate that an exact interval is still bookable."""
    now = now or now_utc()
    tzname = business["timezone"]
    local_date = utc_to_local(start_at, tzname).date()
    horizon_days = int(business.get("booking_horizon_days", 90))
    if start_at <= now:
        return False
    if local_date > (utc_to_local(now, tzname).date() + timedelta(days=horizon_days)):
        return False
    windows = windows_to_utc(
        effective_local_windows(
            business=business,
            rules=rules,
            exceptions=exceptions,
            local_date=local_date,
        ),
        local_date,
        tzname,
    )
    if not any(w.start <= start_at and end_at <= w.end for w in windows):
        return False
    buf_before = timedelta(minutes=int(service.get("buffer_before_minutes") or 0))
    buf_after = timedelta(minutes=int(service.get("buffer_after_minutes") or 0))
    busy = [(a["start_at"], a["end_at"]) for a in appointments if a.get("status") == "confirmed"]
    return not _blocked(start_at, end_at, busy, buf_before, buf_after)
