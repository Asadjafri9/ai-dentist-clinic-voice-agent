"""MongoDB integration tests — require TEST_MONGODB_URI (replica set).

Run: TEST_MONGODB_URI=... uv run pytest tests/test_integration_booking.py
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta

import pytest

from app.services import booking as booking_svc
from app.services import offers as offer_svc
from app.services.timeutil import now_utc

UTC = UTC
SECRET = "test-offer-secret"

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_MONGODB_URI") and not os.environ.get("MONGODB_URI"),
    reason="needs MongoDB URI",
)


def _next_weekday(now: datetime, weekday: int) -> datetime:
    """Next UTC instant of the given weekday at 13:00 UTC."""
    days = (weekday - now.weekday()) % 7 or 7
    d = (now + timedelta(days=days)).date()
    return datetime(d.year, d.month, d.day, 13, 0, tzinfo=UTC)


def _offer(db_business, service, provider, start, end):
    token, exp = offer_svc.mint_offer(
        secret=SECRET,
        ttl_seconds=300,
        business_id=db_business["_id"],
        service_id=service["_id"],
        provider_id=provider["_id"],
        start_at=start,
        end_at=end,
        schedule_version=0,
    )
    return token


async def test_successful_booking_creates_records(db, seeded):
    start = _next_weekday(now_utc(), 0)  # next Monday 13:00 UTC
    end = start + timedelta(hours=1)
    token = _offer(seeded["business"], seeded["service60"], seeded["provider"], start, end)

    res = await booking_svc.book_appointment(
        db,
        business=seeded["business"],
        call_id="cal_1",
        vapi_call_id="vcal_1",
        patient_name="John Smith",
        callback_phone="+12145551234",
        offer_token=token,
        patient_confirmed=True,
        offer_secret=SECRET,
    )
    assert res["code"] == booking_svc.BOOKED

    appt = await db["appointments"].find_one({"_id": res["appointment_id"]})
    assert appt["status"] == "confirmed"
    assert appt["patient_name"] == "John Smith"
    patient = await db["patients"].find_one({"_id": appt["patient_id"]})
    assert patient["phone"] == "+12145551234"
    audit = await db["audit_events"].find_one(
        {"target_id": appt["_id"], "action": "appointment.booked"}
    )
    assert audit is not None


async def test_idempotent_replay_returns_same(db, seeded):
    start = _next_weekday(now_utc(), 0)
    end = start + timedelta(hours=1)
    token = _offer(seeded["business"], seeded["service60"], seeded["provider"], start, end)

    kw = dict(
        business=seeded["business"], call_id="cal_dup", vapi_call_id="vcal_dup",
        patient_name="John Smith", callback_phone="+12145551234",
        offer_token=token, patient_confirmed=True, offer_secret=SECRET,
    )
    r1 = await booking_svc.book_appointment(db, **kw)
    r2 = await booking_svc.book_appointment(db, **kw)
    assert r1["code"] == booking_svc.BOOKED
    assert r2["code"] == booking_svc.ALREADY_BOOKED
    assert r1["appointment_id"] == r2["appointment_id"]
    assert await db["appointments"].count_documents({"business_id": "biz_it"}) == 1


async def test_concurrent_last_slot_exactly_one_wins(db, seeded):
    start = _next_weekday(now_utc(), 0)
    end = start + timedelta(hours=1)
    token = _offer(seeded["business"], seeded["service60"], seeded["provider"], start, end)

    async def attempt(call_id: str, name: str, phone: str):
        return await booking_svc.book_appointment(
            db, business=seeded["business"], call_id=call_id,
            vapi_call_id=f"v{call_id}", patient_name=name,
            callback_phone=phone, offer_token=token,
            patient_confirmed=True, offer_secret=SECRET,
        )

    results = await asyncio.gather(
        attempt("cal_a", "Alice A", "+12145550001"),
        attempt("cal_b", "Bob B", "+12145550002"),
        attempt("cal_c", "Carol C", "+12145550003"),
    )
    codes = [r["code"] for r in results]
    assert codes.count(booking_svc.BOOKED) == 1
    assert codes.count(booking_svc.SLOT_UNAVAILABLE) == 2
    count = await db["appointments"].count_documents(
        {"business_id": "biz_it", "provider_id": "prv_it", "status": "confirmed"}
    )
    assert count == 1


async def test_different_providers_same_time_ok(db, seeded):
    start = _next_weekday(now_utc(), 1)
    end = start + timedelta(hours=1)
    for i, prv in enumerate([seeded["provider"], seeded["provider2"]]):
        token = _offer(seeded["business"], seeded["service60"], prv, start, end)
        res = await booking_svc.book_appointment(
            db, business=seeded["business"], call_id=f"cal_{i}",
            vapi_call_id=f"vcal_{i}", patient_name=f"P{i}",
            callback_phone=f"+121455500{i}0", offer_token=token,
            patient_confirmed=True, offer_secret=SECRET,
        )
        assert res["code"] == booking_svc.BOOKED


async def test_overlapping_60_blocks_30(db, seeded):
    start = _next_weekday(now_utc(), 2)
    # Book a 60-min cleaning at start.
    token60 = _offer(
        seeded["business"], seeded["service60"], seeded["provider"],
        start, start + timedelta(hours=1),
    )
    r = await booking_svc.book_appointment(
        db, business=seeded["business"], call_id="cal_60", vapi_call_id="v60",
        patient_name="Sixty", callback_phone="+12145550060",
        offer_token=token60, patient_confirmed=True, offer_secret=SECRET,
    )
    assert r["code"] == booking_svc.BOOKED

    # A 30-min exam overlapping the second half must fail.
    overlap = start + timedelta(minutes=30)
    token30 = _offer(
        seeded["business"], seeded["service30"], seeded["provider"],
        overlap, overlap + timedelta(minutes=30),
    )
    r2 = await booking_svc.book_appointment(
        db, business=seeded["business"], call_id="cal_30", vapi_call_id="v30",
        patient_name="Thirty", callback_phone="+12145550030",
        offer_token=token30, patient_confirmed=True, offer_secret=SECRET,
    )
    assert r2["code"] == booking_svc.SLOT_UNAVAILABLE


async def test_expired_and_tampered_offers(db, seeded):
    start = _next_weekday(now_utc(), 3)
    end = start + timedelta(hours=1)
    expired_token, _ = offer_svc.mint_offer(
        secret=SECRET, ttl_seconds=-10, business_id="biz_it",
        service_id="svc_it_clean", provider_id="prv_it",
        start_at=start, end_at=end, schedule_version=0,
    )
    r = await booking_svc.book_appointment(
        db, business=seeded["business"], call_id="cal_e", vapi_call_id="ve",
        patient_name="E", callback_phone="+12145550001",
        offer_token=expired_token, patient_confirmed=True, offer_secret=SECRET,
    )
    assert r["code"] == booking_svc.OFFER_EXPIRED

    good = _offer(seeded["business"], seeded["service60"], seeded["provider"], start, end)
    r2 = await booking_svc.book_appointment(
        db, business=seeded["business"], call_id="cal_t", vapi_call_id="vt",
        patient_name="T", callback_phone="+12145550001",
        offer_token=good[:-3] + "zzz", patient_confirmed=True, offer_secret=SECRET,
    )
    assert r2["code"] == booking_svc.INVALID_DETAILS


async def test_requires_confirmation_and_valid_phone(db, seeded):
    start = _next_weekday(now_utc(), 3)
    end = start + timedelta(hours=1)
    token = _offer(seeded["business"], seeded["service60"], seeded["provider"], start, end)
    base = dict(
        business=seeded["business"], call_id="cal_x", vapi_call_id="vx",
        patient_name="X", callback_phone="+12145551234",
        offer_token=token, offer_secret=SECRET,
    )
    r = await booking_svc.book_appointment(db, patient_confirmed=False, **base)
    assert r["code"] == booking_svc.INVALID_DETAILS

    r2 = await booking_svc.book_appointment(
        db, patient_confirmed=True, **{**base, "callback_phone": "abc"}
    )
    assert r2["code"] == booking_svc.INVALID_DETAILS
    assert r2.get("field") == "callback_phone"


async def test_cancellation_releases_slot(db, seeded):
    from app.repositories.clinical_repo import AppointmentRepo

    start = _next_weekday(now_utc(), 4)
    end = start + timedelta(hours=1)
    token = _offer(seeded["business"], seeded["service60"], seeded["provider"], start, end)
    r = await booking_svc.book_appointment(
        db, business=seeded["business"], call_id="cal_cxl", vapi_call_id="vcxl",
        patient_name="Cx", callback_phone="+12145550001",
        offer_token=token, patient_confirmed=True, offer_secret=SECRET,
    )
    assert r["code"] == booking_svc.BOOKED
    repo = AppointmentRepo(db)
    res = await repo.update_status("biz_it", r["appointment_id"], "confirmed", "cancelled")
    assert res.modified_count == 1
    # Slot is free again — second booking of same interval succeeds.
    token2 = _offer(seeded["business"], seeded["service60"], seeded["provider"], start, end)
    r2 = await booking_svc.book_appointment(
        db, business=seeded["business"], call_id="cal_cxl2", vapi_call_id="vcxl2",
        patient_name="Cx2", callback_phone="+12145550002",
        offer_token=token2, patient_confirmed=True, offer_secret=SECRET,
    )
    assert r2["code"] == booking_svc.BOOKED


async def test_cross_tenant_offer_rejected(db, seeded):
    start = _next_weekday(now_utc(), 0)
    end = start + timedelta(hours=1)
    # Offer minted for a different business must be rejected.
    token = _offer(
        {"_id": "biz_other"}, seeded["service60"], seeded["provider"], start, end
    )
    r = await booking_svc.book_appointment(
        db, business=seeded["business"], call_id="cal_xt", vapi_call_id="vxt",
        patient_name="X", callback_phone="+12145550001",
        offer_token=token, patient_confirmed=True, offer_secret=SECRET,
    )
    assert r["code"] == booking_svc.INVALID_DETAILS
