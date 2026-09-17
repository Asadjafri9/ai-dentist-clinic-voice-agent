"""Call lifecycle and backend-derived outcome logic.

`appointment_booked` is derived only from an authoritative appointment
link — never from post-call model analysis.
"""

from __future__ import annotations

from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from app.repositories.clinical_repo import AppointmentRepo
from app.schemas.common import SAFETY_SCRIPT_MARKER, CallOutcome


def derive_outcome(
    call_doc: dict[str, Any], appointment: dict[str, Any] | None
) -> str:
    """Deterministic backend-derived outcome."""
    if appointment is not None:
        return CallOutcome.APPOINTMENT_BOOKED

    transcript = (call_doc.get("transcript") or "").lower()
    tools = set(call_doc.get("tool_calls") or [])
    ended_reason = call_doc.get("ended_reason") or ""
    duration = call_doc.get("duration_seconds")

    if SAFETY_SCRIPT_MARKER in transcript:
        return CallOutcome.SAFETY_REDIRECT
    if ended_reason in {
        "customer-did-not-answer",
        "customer-busy",
        "silence-timed-out",
    } or (duration is not None and duration < 10 and not tools):
        return CallOutcome.CALLER_DISCONNECTED
    if "book_appointment" in tools:
        return CallOutcome.BOOKING_FAILED
    if "get_available_slots" in tools:
        return CallOutcome.NO_AVAILABLE_SLOT
    if tools & {"get_clinic_info", "get_services"}:
        return CallOutcome.INFORMATION_ONLY
    if not tools and duration:
        return CallOutcome.INFORMATION_ONLY
    return CallOutcome.UNKNOWN


async def link_appointment_for_call(
    db: AsyncDatabase, business_id: str, call_id: str  # type: ignore[type-arg]
) -> dict[str, Any] | None:
    return await AppointmentRepo(db).col.find_one(
        {"business_id": business_id, "call_id": call_id}
    )
