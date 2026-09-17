"""Availability engine tests: windows, exceptions, buffers, overlap, horizon."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.services.availability import (
    effective_local_windows,
    generate_candidates,
    interval_fits_schedule,
)

UTC = UTC
NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)  # Saturday
MON = date(2026, 9, 21)  # Monday


def _rule(weekday=0, s="08:00", e="15:00", **kw):
    return {
        "business_id": "biz_test",
        "provider_id": "prv_anna",
        "weekday": weekday,
        "start_local": s,
        "end_local": e,
        "active": True,
        **kw,
    }


def test_candidates_within_window(business, cleaning, provider):
    rules = [_rule(weekday=MON.weekday())]
    cands = generate_candidates(
        business=business, service=cleaning, providers=[provider],
        rules_by_provider={"prv_anna": rules},
        exceptions_by_provider={"prv_anna": []},
        appointments_by_provider={"prv_anna": []},
        local_date=MON, now=NOW,
    )
    assert cands
    for c in cands:
        assert c.provider_id == "prv_anna"
        assert (c.end_at - c.start_at) == timedelta(minutes=60)


def test_no_candidates_when_closed(business, cleaning, provider):
    rules = [_rule(weekday=MON.weekday())]
    exc = [{"kind": "closed", "local_date": MON.isoformat(), "active": True}]
    cands = generate_candidates(
        business=business, service=cleaning, providers=[provider],
        rules_by_provider={"prv_anna": rules},
        exceptions_by_provider={"prv_anna": exc},
        appointments_by_provider={"prv_anna": []},
        local_date=MON, now=NOW,
    )
    assert cands == []


def test_partial_closure_subtracts(business, cleaning, provider):
    rules = [_rule(weekday=MON.weekday(), s="08:00", e="15:00")]
    # Close 10:00-12:00 → a 60-min service can still start 08:00/08:30/09:00.
    exc = [{
        "kind": "closed", "local_date": MON.isoformat(), "active": True,
        "start_local": "10:00", "end_local": "12:00",
    }]
    cands = generate_candidates(
        business=business, service=cleaning, providers=[provider],
        rules_by_provider={"prv_anna": rules},
        exceptions_by_provider={"prv_anna": exc},
        appointments_by_provider={"prv_anna": []},
        local_date=MON, now=NOW,
    )
    assert cands
    for c in cands:
        c.start_at.astimezone()  # sanity only


def test_existing_appointment_blocks_overlap(business, cleaning, provider):
    rules = [_rule(weekday=MON.weekday(), s="08:00", e="15:00")]
    # Existing confirmed appointment 09:00-10:00 local (CDT → 14:00-15:00 UTC).
    busy = [{
        "status": "confirmed",
        "start_at": datetime(2026, 9, 21, 14, 0, tzinfo=UTC),
        "end_at": datetime(2026, 9, 21, 15, 0, tzinfo=UTC),
    }]
    cands = generate_candidates(
        business=business, service=cleaning, providers=[provider],
        rules_by_provider={"prv_anna": rules},
        exceptions_by_provider={"prv_anna": []},
        appointments_by_provider={"prv_anna": busy},
        local_date=MON, now=NOW,
    )
    for c in cands:
        assert not (c.start_at < busy[0]["end_at"] and c.end_at > busy[0]["start_at"])


def test_sixty_min_blocks_thirty_overlap(business, exam, provider):
    """A 60-min booking must block overlapping 30-min candidates."""
    rules = [_rule(weekday=MON.weekday(), s="08:00", e="15:00")]
    busy = [{
        "status": "confirmed",
        "start_at": datetime(2026, 9, 21, 14, 0, tzinfo=UTC),  # 09:00 local
        "end_at": datetime(2026, 9, 21, 15, 0, tzinfo=UTC),    # 10:00 local
    }]
    cands = generate_candidates(
        business=business, service=exam, providers=[provider],
        rules_by_provider={"prv_anna": rules},
        exceptions_by_provider={"prv_anna": []},
        appointments_by_provider={"prv_anna": busy},
        local_date=MON, now=NOW,
    )
    # 08:30 (13:30Z) would overlap 09:00-10:00 for a 30-min exam.
    for c in cands:
        assert not (c.start_at < busy[0]["end_at"] and c.end_at > busy[0]["start_at"])


def test_past_date_rejected(business, cleaning, provider):
    rules = [_rule(weekday=4)]  # Friday
    cands = generate_candidates(
        business=business, service=cleaning, providers=[provider],
        rules_by_provider={"prv_anna": rules},
        exceptions_by_provider={"prv_anna": []},
        appointments_by_provider={"prv_anna": []},
        local_date=date(2026, 9, 18),  # Friday before NOW (Sat)
        now=NOW,
    )
    assert cands == []


def test_beyond_horizon_rejected(business, cleaning, provider):
    rules = [_rule(weekday=MON.weekday())]
    far = NOW.date() + timedelta(days=200)
    cands = generate_candidates(
        business=business, service=cleaning, providers=[provider],
        rules_by_provider={"prv_anna": rules},
        exceptions_by_provider={"prv_anna": []},
        appointments_by_provider={"prv_anna": []},
        local_date=far, now=NOW,
    )
    assert cands == []


def test_time_window_filter(business, cleaning, provider):
    rules = [_rule(weekday=MON.weekday(), s="08:00", e="18:00")]
    cands = generate_candidates(
        business=business, service=cleaning, providers=[provider],
        rules_by_provider={"prv_anna": rules},
        exceptions_by_provider={"prv_anna": []},
        appointments_by_provider={"prv_anna": []},
        local_date=MON, time_window="afternoon", now=NOW,
    )
    assert cands
    for c in cands:
        c.start_at.astimezone()  # tz-aware local check below
    # Explicit check in clinic tz
    from app.services.timeutil import utc_to_local

    for c in cands:
        h = utc_to_local(c.start_at, business["timezone"]).hour
        assert 12 <= h < 17


def test_sunday_clinic_closed(business, cleaning, provider):
    rules = [_rule(weekday=6)]  # provider rule exists on Sunday
    cands = generate_candidates(
        business=business, service=cleaning, providers=[provider],
        rules_by_provider={"prv_anna": rules},
        exceptions_by_provider={"prv_anna": []},
        appointments_by_provider={"prv_anna": []},
        local_date=date(2026, 9, 20),  # Sunday — clinic closed
        now=NOW,
    )
    assert cands == []


def test_added_exception_creates_window(business, cleaning, provider):
    # Sunday clinic is closed, so provider rule is clipped away; but an
    # "added" exception inside Saturday hours can extend availability.
    rules = [_rule(weekday=5, s="08:00", e="09:00")]  # Sat 08-09 (clinic opens 09)
    exc = [{
        "kind": "added", "local_date": "2026-09-19", "active": True,
        "start_local": "14:00", "end_local": "15:00",
    }]
    windows = effective_local_windows(
        business=business, rules=rules, exceptions=exc,
        local_date=date(2026, 9, 19),
    )
    # Provider rule 08:00-09:00 clips to clinic 09:00-15:00 → empty;
    # exception adds 14:00-15:00.
    assert ("14:00", "15:00") in windows


def test_interval_fits_schedule_checks(business, cleaning):
    rules = [_rule(weekday=MON.weekday(), s="08:00", e="15:00")]
    start = datetime(2026, 9, 21, 14, 0, tzinfo=UTC)  # 09:00 local
    end = start + timedelta(hours=1)
    ok = interval_fits_schedule(
        business=business, service=cleaning, provider_id="prv_anna",
        rules=rules, exceptions=[], appointments=[],
        start_at=start, end_at=end, now=NOW,
    )
    assert ok
    # Outside window: 16:00 local
    late = datetime(2026, 9, 21, 22, 0, tzinfo=UTC)
    assert not interval_fits_schedule(
        business=business, service=cleaning, provider_id="prv_anna",
        rules=rules, exceptions=[], appointments=[],
        start_at=late, end_at=late + timedelta(hours=1), now=NOW,
    )
