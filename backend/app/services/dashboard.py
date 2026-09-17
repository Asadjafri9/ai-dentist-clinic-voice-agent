"""Dashboard metric computation.

Booking-rate denominator: completed calls whose primary intent was
booking, excluding information-only, safety redirect, unsupported
request, and system-unavailable calls.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from app.schemas.common import CallOutcome
from app.services.timeutil import now_utc, utc_to_local

NON_BOOKING_OUTCOMES = {
    CallOutcome.INFORMATION_ONLY,
    CallOutcome.SAFETY_REDIRECT,
    CallOutcome.UNSUPPORTED_REQUEST,
}


async def dashboard_summary(
    db: AsyncDatabase, business: dict[str, Any], date_str: str | None
) -> dict[str, Any]:  # type: ignore[type-arg]
    tzname = business["timezone"]
    if date_str:
        day = datetime.fromisoformat(date_str).date()
    else:
        day = utc_to_local(now_utc(), tzname).date()
    day_start, day_end = _day_bounds_utc(day, tzname)

    calls_today = await db["calls"].count_documents(
        {"business_id": business["_id"], "created_at": {"$gte": day_start, "$lt": day_end}}
    )
    booked_today = await db["appointments"].count_documents(
        {
            "business_id": business["_id"],
            "source": "voice",
            "created_at": {"$gte": day_start, "$lt": day_end},
        }
    )
    eligible_calls = await db["calls"].count_documents(
        {
            "business_id": business["_id"],
            "created_at": {"$gte": day_start, "$lt": day_end},
            "outcome": {"$nin": list(NON_BOOKING_OUTCOMES | {CallOutcome.UNKNOWN})},
        }
    )
    upcoming = (
        await db["appointments"]
        .find(
            {
                "business_id": business["_id"],
                "status": "confirmed",
                "start_at": {"$gte": now_utc()},
            }
        )
        .sort("start_at", 1)
        .limit(10)
        .to_list(None)
    )
    return {
        "date": day.isoformat(),
        "timezone": tzname,
        "calls_today": calls_today,
        "ai_booked_appointments": booked_today,
        "booking_rate": (booked_today / eligible_calls) if eligible_calls else None,
        "eligible_calls": eligible_calls,
        "upcoming": [_appt_view(a) for a in upcoming],
    }


async def activity_feed(
    db: AsyncDatabase, business_id: str, *, cursor: str | None, limit: int  # type: ignore[type-arg]
) -> tuple[list[dict[str, Any]], str | None]:
    q: dict[str, Any] = {"business_id": business_id}
    if cursor:
        q["_id"] = {"$lt": cursor}
    items = (
        await db["audit_events"]
        .find(q)
        .sort([("created_at", -1), ("_id", -1)])
        .limit(limit + 1)
        .to_list(None)
    )
    next_cursor = items[-1]["_id"] if len(items) > limit else None
    return items[:limit], next_cursor


def _day_bounds_utc(day, tzname: str):
    from app.services.timeutil import local_to_utc

    start = local_to_utc(day, "00:00", tzname)
    end = start + timedelta(days=1)
    return start, end


def _appt_view(a: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": a["_id"],
        "patient_name": a.get("patient_name"),
        "provider_id": a.get("provider_id"),
        "service_id": a.get("service_id"),
        "start_at": a["start_at"].isoformat(),
        "end_at": a["end_at"].isoformat(),
        "status": a.get("status"),
        "source": a.get("source"),
    }
