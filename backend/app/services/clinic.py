"""Clinic-info and service catalog payloads for the voice tools.

The assistant may answer only from what these functions return.
"""

from __future__ import annotations

from typing import Any

from app.services import availability as avail
from app.services.timeutil import now_utc, utc_to_local


def clinic_info_payload(business: dict[str, Any]) -> dict[str, Any]:
    tzname = business["timezone"]
    now = now_utc()
    local_now = utc_to_local(now, tzname)
    hours = business.get("business_hours") or {}
    today_key = avail.WEEKDAY_KEYS[local_now.weekday()]
    today = hours.get(today_key) or {}
    weekly = {
        k: (
            "Closed"
            if (v or {}).get("closed")
            else f"{(v or {}).get('open', '')}-{(v or {}).get('close', '')}"
        )
        for k, v in hours.items()
    }
    return {
        "ok": True,
        "name": business.get("name"),
        "address": business.get("address"),
        "phone": business.get("phone"),
        "timezone": tzname,
        "current_local_time": local_now.strftime("%A, %B %-d, %Y at %-I:%M %p"),
        "today_hours": (
            "Closed"
            if today.get("closed")
            else f"{today.get('open', '')}-{today.get('close', '')}"
        ),
        "weekly_hours": weekly,
        "faqs": business.get("faqs") or [],
        "features": {
            "collect_email": bool(business.get("collect_email")),
            "voice_booking": True,
        },
    }


def services_payload(
    services: list[dict[str, Any]], providers: list[dict[str, Any]]
) -> dict[str, Any]:
    out = []
    for s in services:
        eligible = [
            p["name"]
            for p in providers
            if s["_id"] in (p.get("service_ids") or [])
        ]
        out.append(
            {
                "slug": s["slug"],
                "display_name": s["display_name"],
                "description": s.get("description"),
                "aliases": s.get("aliases") or [],
                "duration_minutes": s["duration_minutes"],
                "providers": eligible,
            }
        )
    return {"ok": True, "services": out}
