"""Shared API schema helpers."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class OkEnvelope(BaseModel):
    success: bool = True
    data: Any = None


class Page(BaseModel):
    items: list[Any]
    next_cursor: str | None = None


def ok(data: Any) -> dict[str, Any]:
    return {"success": True, "data": data}


def ok_page(
    items: list[Any], next_cursor: str | None, extra: dict[str, Any] | None = None
) -> dict[str, Any]:
    data: dict[str, Any] = {"items": items, "next_cursor": next_cursor}
    if extra:
        data.update(extra)
    return {"success": True, "data": data}


class TimeWindow(str):
    pass


class DayHours(BaseModel):
    open: str = Field(pattern=r"^\d{2}:\d{2}$")
    close: str = Field(pattern=r"^\d{2}:\d{2}$")
    closed: bool = False


class WeeklyHours(BaseModel):
    mon: DayHours = DayHours(open="08:00", close="18:00")
    tue: DayHours = DayHours(open="08:00", close="18:00")
    wed: DayHours = DayHours(open="08:00", close="18:00")
    thu: DayHours = DayHours(open="08:00", close="18:00")
    fri: DayHours = DayHours(open="08:00", close="18:00")
    sat: DayHours = DayHours(open="09:00", close="15:00")
    sun: DayHours = DayHours(open="00:00", close="00:00", closed=True)

    def for_weekday(self, weekday: int) -> DayHours:
        return [self.mon, self.tue, self.wed, self.thu, self.fri, self.sat, self.sun][weekday]


class FaqEntry(BaseModel):
    question: str
    answer: str


class AppointmentStatus:
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"

    ALLOWED = {CONFIRMED, CANCELLED, COMPLETED}
    TRANSITIONS = {CONFIRMED: {CANCELLED, COMPLETED}, CANCELLED: set(), COMPLETED: set()}

    @classmethod
    def can_transition(cls, current: str, target: str) -> bool:
        return target in cls.TRANSITIONS.get(current, set())


class CallOutcome:
    APPOINTMENT_BOOKED = "appointment_booked"
    INFORMATION_ONLY = "information_only"
    UNSUPPORTED_REQUEST = "unsupported_request"
    NO_AVAILABLE_SLOT = "no_available_slot"
    CALLER_DISCONNECTED = "caller_disconnected"
    BOOKING_FAILED = "booking_failed"
    SAFETY_REDIRECT = "safety_redirect"
    UNKNOWN = "unknown"

    ALLOWED = {
        APPOINTMENT_BOOKED,
        INFORMATION_ONLY,
        UNSUPPORTED_REQUEST,
        NO_AVAILABLE_SLOT,
        CALLER_DISCONNECTED,
        BOOKING_FAILED,
        SAFETY_REDIRECT,
        UNKNOWN,
    }


SAFETY_SCRIPT_MARKER = "can't assess or treat emergencies"
