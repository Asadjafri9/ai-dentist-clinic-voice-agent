"""Security primitive tests: tokens, phones, CSRF."""

from __future__ import annotations

import pytest

from app.core.errors import ValidationError
from app.core.security import (
    constant_time_equals,
    normalize_phone,
    phone_suffix,
    sign_payload,
    try_normalize_phone,
    verify_payload,
)


def test_signed_payload_roundtrip():
    token = sign_payload({"a": 1, "b": "x"}, "secret")
    assert verify_payload(token, "secret") == {"a": 1, "b": "x"}


def test_signed_payload_tamper_rejected():
    token = sign_payload({"a": 1}, "secret")
    assert verify_payload(token + "x", "secret") is None
    assert verify_payload(token, "wrong") is None
    assert verify_payload("garbage", "secret") is None
    assert verify_payload("a.b.c", "secret") is None


def test_phone_normalization():
    assert normalize_phone("(214) 555-1234") == "+12145551234"
    assert normalize_phone("+1 214 555 1234") == "+12145551234"
    assert normalize_phone("2145551234") == "+12145551234"


def test_phone_invalid():
    with pytest.raises(ValidationError):
        normalize_phone("123")
    with pytest.raises(ValidationError):
        normalize_phone("not a phone")
    assert try_normalize_phone("garbage") is None
    assert try_normalize_phone(None) is None


def test_phone_suffix():
    assert phone_suffix("+12145551234") == "1234"
    assert phone_suffix(None) is None


def test_constant_time():
    assert constant_time_equals("abc", "abc")
    assert not constant_time_equals("abc", "abd")
