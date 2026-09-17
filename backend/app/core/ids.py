"""Opaque ID generation. IDs are opaque strings at API boundaries."""

from __future__ import annotations

import secrets


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(12)}"


def business_id() -> str:
    return new_id("biz")


def admin_id() -> str:
    return new_id("adm")


def service_id() -> str:
    return new_id("svc")


def provider_id() -> str:
    return new_id("prv")


def patient_id() -> str:
    return new_id("pat")


def appointment_id() -> str:
    return new_id("apt")


def call_id() -> str:
    return new_id("cal")


def event_id() -> str:
    return new_id("evt")


def job_id() -> str:
    return new_id("job")


def rule_id() -> str:
    return new_id("rul")


def exception_id() -> str:
    return new_id("exc")


def session_token() -> str:
    return secrets.token_urlsafe(32)


def booking_intent_id(call_id: str, tool_call_id: str) -> str:
    """One booking intent per trusted (call, tool call) pair.

    Deterministic so duplicate tool deliveries map to the same intent.
    """
    import hashlib

    digest = hashlib.sha256(f"{call_id}:{tool_call_id}".encode()).hexdigest()[:24]
    return f"bi_{digest}"
