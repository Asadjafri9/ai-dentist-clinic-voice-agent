"""Admin API request schemas (strict validation)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import FaqEntry, WeeklyHours


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class BusinessPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = None
    address: str | None = None
    timezone: str | None = None
    business_hours: WeeklyHours | None = None
    greeting: str | None = Field(default=None, max_length=2000)
    consent_disclosure: str | None = Field(default=None, max_length=1000)
    faqs: list[FaqEntry] | None = None
    booking_horizon_days: int | None = Field(default=None, ge=1, le=365)
    slot_increment_minutes: int | None = Field(default=None, ge=5, le=120)
    booking_lead_time_minutes: int | None = Field(default=None, ge=0, le=1440)
    transcript_retention_days: int | None = Field(default=None, ge=1, le=365)
    collect_email: bool | None = None


class VoicePatch(BaseModel):
    """Voice-specific settings pushed to the voice provider."""

    greeting: str | None = Field(default=None, max_length=2000)
    consent_disclosure: str | None = Field(default=None, max_length=1000)
    voice_id: str | None = None
    voice_provider: str | None = None


class ServiceCreate(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9_]+$", min_length=2, max_length=64)
    display_name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    aliases: list[str] = Field(default_factory=list)
    duration_minutes: int = Field(ge=5, le=480)
    buffer_before_minutes: int = Field(default=0, ge=0, le=120)
    buffer_after_minutes: int = Field(default=0, ge=0, le=120)
    active: bool = True
    voice_bookable: bool = True


class ServicePatch(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    aliases: list[str] | None = None
    duration_minutes: int | None = Field(default=None, ge=5, le=480)
    buffer_before_minutes: int | None = Field(default=None, ge=0, le=120)
    buffer_after_minutes: int | None = Field(default=None, ge=0, le=120)
    active: bool | None = None
    voice_bookable: bool | None = None
    version: int | None = None


class ProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    title: str | None = None
    service_ids: list[str] = Field(default_factory=list)
    active: bool = True


class ProviderPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    title: str | None = None
    service_ids: list[str] | None = None
    active: bool | None = None
    version: int | None = None


class AvailabilityRuleCreate(BaseModel):
    provider_id: str
    weekday: int = Field(ge=0, le=6)
    start_local: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_local: str = Field(pattern=r"^\d{2}:\d{2}$")
    effective_from: str | None = None  # YYYY-MM-DD
    effective_to: str | None = None
    active: bool = True


class AvailabilityRulePatch(BaseModel):
    weekday: int | None = Field(default=None, ge=0, le=6)
    start_local: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    end_local: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    effective_from: str | None = None
    effective_to: str | None = None
    active: bool | None = None


class AvailabilityExceptionCreate(BaseModel):
    provider_id: str | None = None  # None = clinic-wide
    local_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    kind: Literal["closed", "added"] = "closed"
    start_local: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    end_local: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    reason: str | None = None


class AppointmentStatusPatch(BaseModel):
    status: Literal["cancelled", "completed"]
    idempotency_key: str = Field(min_length=8, max_length=128)
    reason: str | None = Field(default=None, max_length=500)
    allow_early_completion: bool = False
