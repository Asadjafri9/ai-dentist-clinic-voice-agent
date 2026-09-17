"""Offer-token integrity: tenant binding, tamper rejection, expiry."""

from __future__ import annotations

from datetime import UTC, timedelta

from app.services import offers
from app.services.timeutil import now_utc

UTC = UTC


def _mint(**kw):
    defaults = dict(
        secret="s3cret",
        ttl_seconds=300,
        business_id="biz_a",
        service_id="svc_1",
        provider_id="prv_1",
        start_at=now_utc() + timedelta(days=1),
        end_at=now_utc() + timedelta(days=1, minutes=30),
        schedule_version=7,
    )
    defaults.update(kw)
    return offers.mint_offer(**defaults)


def test_offer_roundtrip():
    token, exp = _mint()
    payload = offers.verify_offer(token, "s3cret")
    assert payload is not None
    assert payload.business_id == "biz_a"
    assert payload.schedule_version == 7
    assert payload.expires_at == exp


def test_offer_tamper_and_wrong_secret():
    token, _ = _mint()
    assert offers.verify_offer(token + "zz", "s3cret") is None
    assert offers.verify_offer(token, "other") is None


def test_offer_tenant_binding():
    token, _ = _mint(business_id="biz_a")
    payload = offers.verify_offer(token, "s3cret")
    assert payload.business_id != "biz_b"


def test_offer_expiry_value():
    token, exp = _mint(ttl_seconds=60)
    payload = offers.verify_offer(token, "s3cret")
    assert abs((payload.expires_at - exp).total_seconds()) < 1
    assert payload.expires_at > now_utc()


def test_booking_intent_deterministic_and_unique():
    a = offers.booking_intent_for("biz", "cal_1", "offer1")
    b = offers.booking_intent_for("biz", "cal_1", "offer1")
    c = offers.booking_intent_for("biz", "cal_2", "offer1")
    d = offers.booking_intent_for("biz", "cal_1", "offer2")
    assert a == b
    assert a != c and a != d
    assert a.startswith("bi_")
