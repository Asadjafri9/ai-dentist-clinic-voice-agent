"""Voice tool input/output contracts.

Every tool response uses a small stable JSON shape. Failures carry
`code`, `retryable`, and a caller-safe `spoken_message`. Raw exceptions
never become tool output.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class GetClinicInfoInput(BaseModel):
    model_config = {"extra": "forbid"}


class GetServicesInput(BaseModel):
    model_config = {"extra": "forbid"}


TimeWindowName = Literal["morning", "afternoon", "evening", "any"]


class GetAvailableSlotsInput(BaseModel):
    model_config = {"extra": "forbid"}

    service_slug: str
    preferred_date: str | None = None  # YYYY-MM-DD in clinic timezone
    time_window: TimeWindowName = "any"
    provider_name: str | None = None


class BookAppointmentInput(BaseModel):
    model_config = {"extra": "forbid"}

    patient_name: str = Field(min_length=1, max_length=200)
    callback_phone: str = Field(min_length=3, max_length=32)
    offer_token: str
    patient_confirmed: bool = False
    booking_intent_id: str | None = None  # accepted but overridden server-side


class ToolFailure(BaseModel):
    code: str
    retryable: bool
    spoken_message: str

    def dump(self) -> dict[str, Any]:
        return {
            "ok": False,
            "code": self.code,
            "retryable": self.retryable,
            "spoken_message": self.spoken_message,
        }


def tool_failure(code: str, spoken_message: str, retryable: bool = False) -> dict[str, Any]:
    return ToolFailure(code=code, retryable=retryable, spoken_message=spoken_message).dump()
