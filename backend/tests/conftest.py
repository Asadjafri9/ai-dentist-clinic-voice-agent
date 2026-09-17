"""Test fixtures.

Unit tests run without MongoDB. Integration tests need a MongoDB URI
with transactions (replica set) — set TEST_MONGODB_URI or they skip.
"""

from __future__ import annotations

import os
from datetime import UTC
from typing import Any

import pytest

UTC = UTC
TZ = "America/Chicago"


@pytest.fixture
def business() -> dict[str, Any]:
    return {
        "_id": "biz_test",
        "slug": "brightsmile-dental",
        "name": "BrightSmile Dental",
        "timezone": TZ,
        "phone": "+12145550100",
        "address": "4100 Maple Ave, Dallas, TX",
        "active": True,
        "schedule_version": 3,
        "booking_horizon_days": 90,
        "slot_increment_minutes": 30,
        "booking_lead_time_minutes": 0,
        "business_hours": {
            "mon": {"open": "08:00", "close": "18:00", "closed": False},
            "tue": {"open": "08:00", "close": "18:00", "closed": False},
            "wed": {"open": "08:00", "close": "18:00", "closed": False},
            "thu": {"open": "08:00", "close": "18:00", "closed": False},
            "fri": {"open": "08:00", "close": "18:00", "closed": False},
            "sat": {"open": "09:00", "close": "15:00", "closed": False},
            "sun": {"open": "00:00", "close": "00:00", "closed": True},
        },
    }


@pytest.fixture
def cleaning() -> dict[str, Any]:
    return {
        "_id": "svc_clean",
        "business_id": "biz_test",
        "slug": "dental_cleaning",
        "display_name": "Dental Cleaning",
        "duration_minutes": 60,
        "buffer_before_minutes": 0,
        "buffer_after_minutes": 0,
        "active": True,
        "voice_bookable": True,
    }


@pytest.fixture
def exam() -> dict[str, Any]:
    return {
        "_id": "svc_exam",
        "business_id": "biz_test",
        "slug": "dental_exam",
        "display_name": "Routine Dental Exam",
        "duration_minutes": 30,
        "buffer_before_minutes": 0,
        "buffer_after_minutes": 0,
        "active": True,
        "voice_bookable": True,
    }


@pytest.fixture
def provider() -> dict[str, Any]:
    return {
        "_id": "prv_anna",
        "business_id": "biz_test",
        "name": "Anna Lee",
        "title": "Dental Hygienist",
        "service_ids": ["svc_clean", "svc_exam"],
        "active": True,
    }


@pytest.fixture
def weekday_rule() -> dict[str, Any]:
    """Anna works Mon-Fri 08:00-15:00."""
    return {
        "business_id": "biz_test",
        "provider_id": "prv_anna",
        "weekday": 0,  # will be overridden per-test
        "start_local": "08:00",
        "end_local": "15:00",
        "active": True,
    }


# ---------- Integration fixtures ----------

def _test_db_uri() -> str | None:
    uri = os.environ.get("TEST_MONGODB_URI")
    if uri:
        return uri
    env_uri = os.environ.get("MONGODB_URI")
    return env_uri


@pytest.fixture
async def db():
    """A throwaway test database on a real MongoDB deployment."""
    uri = _test_db_uri()
    if not uri:
        pytest.skip("TEST_MONGODB_URI not set")
    import secrets

    from pymongo import AsyncMongoClient

    client = AsyncMongoClient(uri, tz_aware=True)
    name = f"test_{secrets.token_hex(6)}"
    database = client[name]
    from app.db.indexes import ensure_indexes

    await ensure_indexes(database)
    yield database
    # dropDatabase needs elevated Atlas perms; delete docs instead.
    for name_ in await database.list_collection_names():
        await database[name_].delete_many({})
    await client.close()


@pytest.fixture
async def seeded(db):
    """Seed a minimal business/service/provider/rules set into the test db."""
    from app.services.timeutil import now_utc

    biz = {
        "_id": "biz_it",
        "slug": "it-clinic",
        "name": "IT Dental",
        "timezone": TZ,
        "phone": "+12145550100",
        "active": True,
        "schedule_version": 0,
        "booking_horizon_days": 90,
        "slot_increment_minutes": 30,
        "booking_lead_time_minutes": 0,
        "business_hours": {
            k: {"open": "00:00", "close": "23:59", "closed": False}
            for k in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        },
        "created_at": now_utc(),
        "updated_at": now_utc(),
    }
    svc = {
        "_id": "svc_it_clean",
        "business_id": "biz_it",
        "slug": "dental_cleaning",
        "display_name": "Dental Cleaning",
        "duration_minutes": 60,
        "buffer_before_minutes": 0,
        "buffer_after_minutes": 0,
        "active": True,
        "voice_bookable": True,
        "version": 0,
    }
    svc30 = {
        **svc,
        "_id": "svc_it_exam",
        "slug": "dental_exam",
        "display_name": "Routine Dental Exam",
        "duration_minutes": 30,
    }
    prv = {
        "_id": "prv_it",
        "business_id": "biz_it",
        "name": "Dr. Test",
        "service_ids": ["svc_it_clean", "svc_it_exam"],
        "active": True,
        "version": 0,
    }
    prv2 = {
        **prv,
        "_id": "prv_it2",
        "name": "Dr. Test Two",
    }
    await db["businesses"].insert_one(biz)
    await db["services"].insert_many([svc, svc30])
    await db["providers"].insert_many([prv, prv2])
    # Both providers work every weekday 08:00-18:00.
    rules = [
        {
            "_id": f"rul_{pid}_{wd}",
            "business_id": "biz_it",
            "provider_id": pid,
            "weekday": wd,
            "start_local": "08:00",
            "end_local": "18:00",
            "active": True,
        }
        for pid in ("prv_it", "prv_it2")
        for wd in range(7)
    ]
    await db["availability_rules"].insert_many(rules)
    return {
        "business": biz,
        "service60": svc,
        "service30": svc30,
        "provider": prv,
        "provider2": prv2,
    }
