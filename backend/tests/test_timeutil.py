"""Timezone / relative-date conversion tests, including DST."""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.services.timeutil import fmt_local, local_to_utc, utc_to_local

UTC = UTC
CHI = "America/Chicago"


def test_local_to_utc_basic():
    # 2026-09-21 is CDT (UTC-5).
    dt = local_to_utc(date(2026, 9, 21), "08:00", CHI)
    assert dt == datetime(2026, 9, 21, 13, 0, tzinfo=UTC)


def test_dst_spring_forward_gap():
    # 2026-03-08 02:30 does not exist in Chicago (spring forward).
    dt = local_to_utc(date(2026, 3, 8), "02:30", CHI)
    # Shifted forward into a real time.
    back = utc_to_local(dt, CHI)
    assert back.hour in (2, 3)


def test_dst_fall_back():
    # 2026-11-01 01:30 is ambiguous; we take the earlier (CDT) instant.
    dt = local_to_utc(date(2026, 11, 1), "01:30", CHI)
    assert dt.utcoffset() is not None
    assert utc_to_local(dt, CHI).hour == 1


def test_fmt_local_label():
    dt = datetime(2026, 9, 18, 20, 30, tzinfo=UTC)  # 3:30 PM CDT
    label = fmt_local(dt, CHI)
    assert "3:30 PM" in label
    assert "September 18" in label
    assert "Friday" in label
