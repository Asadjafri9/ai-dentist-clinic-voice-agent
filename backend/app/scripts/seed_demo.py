"""Seed the fictional BrightSmile Dental demo clinic.

Usage: uv run python -m app.scripts.seed_demo [--reset]

--reset removes only seed-created demo data (the seeded business and
its configuration), never live call-created records from other
businesses.
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

from app.auth.passwords import hash_password
from app.core import ids
from app.core.config import get_settings
from app.db.client import close_client, init_client
from app.db.indexes import ensure_indexes
from app.services.timeutil import now_utc

CLINIC_SLUG = "brightsmile-dental"

SERVICES: list[dict[str, Any]] = [
    {
        "slug": "dental_cleaning",
        "display_name": "Dental Cleaning",
        "duration_minutes": 60,
        "aliases": ["cleaning", "teeth cleaning", "hygiene visit"],
    },
    {
        "slug": "dental_exam",
        "display_name": "Routine Dental Exam",
        "duration_minutes": 30,
        "aliases": ["exam", "checkup", "check-up", "routine exam"],
    },
    {
        "slug": "dental_consultation",
        "display_name": "Dental Consultation",
        "duration_minutes": 30,
        "aliases": ["consultation", "consult", "new patient visit"],
    },
    {
        "slug": "whitening_consultation",
        "display_name": "Teeth Whitening Consultation",
        "duration_minutes": 30,
        "aliases": ["whitening", "teeth whitening"],
    },
    {
        "slug": "tooth_pain_consultation",
        "display_name": "Tooth Pain Consultation",
        "duration_minutes": 30,
        "aliases": ["tooth pain", "toothache", "pain visit"],
    },
]

PROVIDERS: list[dict[str, Any]] = [
    {"name": "Dr. Sarah Miller", "title": "Dentist"},
    {"name": "Dr. James Carter", "title": "Dentist"},
    {"name": "Anna Lee", "title": "Dental Hygienist"},
]

# Which providers can perform which services (by slug).
PROVIDER_SERVICES = {
    "Dr. Sarah Miller": [
        "dental_exam",
        "dental_consultation",
        "whitening_consultation",
        "tooth_pain_consultation",
    ],
    "Dr. James Carter": [
        "dental_exam",
        "dental_consultation",
        "whitening_consultation",
        "tooth_pain_consultation",
    ],
    "Anna Lee": ["dental_cleaning", "dental_exam"],
}

BUSINESS_HOURS = {
    "mon": {"open": "08:00", "close": "18:00", "closed": False},
    "tue": {"open": "08:00", "close": "18:00", "closed": False},
    "wed": {"open": "08:00", "close": "18:00", "closed": False},
    "thu": {"open": "08:00", "close": "18:00", "closed": False},
    "fri": {"open": "08:00", "close": "18:00", "closed": False},
    "sat": {"open": "09:00", "close": "15:00", "closed": False},
    "sun": {"open": "00:00", "close": "00:00", "closed": True},
}

FAQS = [
    {
        "question": "Where is the clinic located?",
        "answer": "We're at 4100 Maple Avenue, Suite 200, Dallas, Texas.",
    },
    {
        "question": "Do you accept walk-ins?",
        "answer": "We recommend scheduling an appointment so we can reserve time for you.",
    },
    {
        "question": "What should I bring to my first visit?",
        "answer": "Just bring yourself and any questions. We'll handle the rest at check-in.",
    },
]

# Provider recurring windows (weekday -> list of (start,end)).
PROVIDER_SCHEDULE: dict[str, dict[str, Any]] = {
    "Dr. Sarah Miller": {
        "weekdays": [0, 1, 2, 3, 4],
        "windows": [("08:00", "12:00"), ("13:00", "17:00")],
        "saturday": None,
    },
    "Dr. James Carter": {
        "weekdays": [0, 1, 2, 3, 4],
        "windows": [("09:00", "12:00"), ("13:00", "18:00")],
        "saturday": [("09:00", "14:00")],
    },
    "Anna Lee": {
        "weekdays": [0, 1, 2, 3, 4, 5],
        "windows": [("08:00", "15:00")],
        "saturday": [("09:00", "15:00")],
    },
}


async def seed(reset: bool) -> None:
    settings = get_settings()
    client = init_client(settings.mongodb_uri)
    db = client[settings.mongodb_database]
    await ensure_indexes(db)

    if reset:
        biz = await db["businesses"].find_one({"slug": CLINIC_SLUG})
        if biz:
            bid = biz["_id"]
            for col in (
                "services", "providers", "availability_rules",
                "availability_exceptions", "resource_schedule_days",
            ):
                await db[col].delete_many({"business_id": bid})
            await db["admin_users"].delete_many({"business_id": bid})
            print(f"Reset seed config for business {bid} (call-created data kept)")

    business = await db["businesses"].find_one({"slug": CLINIC_SLUG})
    if business is None:
        business = {
            "_id": ids.business_id(),
            "slug": CLINIC_SLUG,
            "name": "BrightSmile Dental",
            "vertical": "dental",
            "assistant_name": "Emily",
            "timezone": "America/Chicago",
            "phone": "+12145550100",
            "address": "4100 Maple Avenue, Suite 200, Dallas, TX 75219",
            "business_hours": BUSINESS_HOURS,
            "faqs": FAQS,
            "greeting": (
                "Thanks for calling BrightSmile Dental. I'm Emily, the AI "
                "receptionist. This call may be transcribed for scheduling and "
                "quality. How can I help?"
            ),
            "consent_disclosure": "This call may be transcribed for scheduling and quality.",
            "booking_horizon_days": settings.booking_horizon_days,
            "slot_increment_minutes": settings.slot_increment_minutes,
            "booking_lead_time_minutes": 30,
            "transcript_retention_days": settings.transcript_retention_days,
            "collect_email": False,
            "active": True,
            "schedule_version": 0,
            "version": 0,
            "voice": {},
            "voice_sync": {"status": "never"},
            # Filled in by deployment wiring:
            "vapi_assistant_id": None,
            "vapi_phone_number_id": None,
            "created_at": now_utc(),
            "updated_at": now_utc(),
        }
        await db["businesses"].insert_one(business)
        print(f"Created business {business['_id']}")
    else:
        print(f"Business exists: {business['_id']}")

    bid = business["_id"]

    # Services
    service_ids: dict[str, str] = {}
    for s in SERVICES:
        existing = await db["services"].find_one({"business_id": bid, "slug": s["slug"]})
        if existing:
            service_ids[s["slug"]] = existing["_id"]
            continue
        doc = {
            "_id": ids.service_id(),
            "business_id": bid,
            **s,
            "description": None,
            "buffer_before_minutes": 0,
            "buffer_after_minutes": 0,
            "active": True,
            "voice_bookable": True,
            "version": 0,
            "created_at": now_utc(),
            "updated_at": now_utc(),
        }
        await db["services"].insert_one(doc)
        service_ids[s["slug"]] = doc["_id"]
    print(f"Services: {len(service_ids)}")

    # Providers
    provider_ids: dict[str, str] = {}
    for p in PROVIDERS:
        existing = await db["providers"].find_one({"business_id": bid, "name": p["name"]})
        svc_ids = [service_ids[s] for s in PROVIDER_SERVICES[p["name"]] if s in service_ids]
        if existing:
            provider_ids[p["name"]] = existing["_id"]
            await db["providers"].update_one(
                {"_id": existing["_id"]}, {"$set": {"service_ids": svc_ids}}
            )
            continue
        doc = {
            "_id": ids.provider_id(),
            "business_id": bid,
            "name": p["name"],
            "title": p["title"],
            "service_ids": svc_ids,
            "active": True,
            "version": 0,
            "created_at": now_utc(),
            "updated_at": now_utc(),
        }
        await db["providers"].insert_one(doc)
        provider_ids[p["name"]] = doc["_id"]
    print(f"Providers: {len(provider_ids)}")

    # Availability rules (recurring provider windows)
    for name, pid in provider_ids.items():
        sched = PROVIDER_SCHEDULE[name]
        for weekday in sched["weekdays"]:
            for start, end in sched["windows"]:
                dup = await db["availability_rules"].find_one(
                    {
                        "business_id": bid,
                        "provider_id": pid,
                        "weekday": weekday,
                        "start_local": start,
                        "end_local": end,
                    }
                )
                if dup:
                    continue
                await db["availability_rules"].insert_one(
                    {
                        "_id": ids.rule_id(),
                        "business_id": bid,
                        "provider_id": pid,
                        "weekday": weekday,
                        "start_local": start,
                        "end_local": end,
                        "effective_from": None,
                        "effective_to": None,
                        "active": True,
                        "created_at": now_utc(),
                        "updated_at": now_utc(),
                    }
                )
        if sched.get("saturday"):
            for start, end in sched["saturday"]:
                dup = await db["availability_rules"].find_one(
                    {
                        "business_id": bid,
                        "provider_id": pid,
                        "weekday": 5,
                        "start_local": start,
                        "end_local": end,
                    }
                )
                if not dup:
                    await db["availability_rules"].insert_one(
                        {
                            "_id": ids.rule_id(),
                            "business_id": bid,
                            "provider_id": pid,
                            "weekday": 5,
                            "start_local": start,
                            "end_local": end,
                            "effective_from": None,
                            "effective_to": None,
                            "active": True,
                            "created_at": now_utc(),
                            "updated_at": now_utc(),
                        }
                    )
    print("Availability rules seeded")

    # Admin user
    if settings.seed_admin_password:
        existing_admin = await db["admin_users"].find_one(
            {"email": settings.seed_admin_email.lower()}
        )
        if existing_admin is None:
            await db["admin_users"].insert_one(
                {
                    "_id": ids.admin_id(),
                    "email": settings.seed_admin_email.lower(),
                    "password_hash": hash_password(settings.seed_admin_password),
                    "business_id": bid,
                    "role": "owner",
                    "active": True,
                    "created_at": now_utc(),
                    "last_login_at": None,
                }
            )
            print(f"Created admin {settings.seed_admin_email}")
        else:
            print("Admin already exists")
    else:
        print("SEED_ADMIN_PASSWORD not set — skipped admin creation")

    print(f"\nDone. business_id={bid}")
    print("Set these in production wiring:")
    print("  vapi_phone_number_id, vapi_assistant_id on the business doc")

    await close_client()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    asyncio.run(seed(args.reset))


if __name__ == "__main__":
    main()
