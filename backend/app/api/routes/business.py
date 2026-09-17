"""Business configuration routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import AdminDep, BusinessDep, CsrfDep, DbDep
from app.core.errors import NotFoundError, ValidationError
from app.repositories.business_repo import BusinessRepo
from app.repositories.system_repo import AuditRepo
from app.schemas.admin import BusinessPatch, VoicePatch
from app.schemas.common import ok
from app.services import jobs as job_svc
from app.services.timeutil import now_utc

router = APIRouter(prefix="/business", tags=["business"])

_SAFE_FIELDS = [
    "name", "phone", "address", "timezone", "business_hours", "greeting",
    "consent_disclosure", "faqs", "booking_horizon_days",
    "slot_increment_minutes", "booking_lead_time_minutes",
    "transcript_retention_days", "collect_email",
]


def _public_business(b: dict) -> dict:
    return {
        "id": b["_id"],
        "name": b.get("name"),
        "slug": b.get("slug"),
        "vertical": b.get("vertical"),
        "timezone": b.get("timezone"),
        "phone": b.get("phone"),
        "address": b.get("address"),
        "business_hours": b.get("business_hours"),
        "greeting": b.get("greeting"),
        "consent_disclosure": b.get("consent_disclosure"),
        "faqs": b.get("faqs") or [],
        "assistant_name": b.get("assistant_name"),
        "booking_horizon_days": b.get("booking_horizon_days"),
        "slot_increment_minutes": b.get("slot_increment_minutes"),
        "booking_lead_time_minutes": b.get("booking_lead_time_minutes"),
        "transcript_retention_days": b.get("transcript_retention_days"),
        "collect_email": b.get("collect_email", False),
        "active": b.get("active", True),
        "vapi_assistant_id": b.get("vapi_assistant_id"),
        "vapi_phone_number_id": b.get("vapi_phone_number_id"),
        "voice_sync": b.get("voice_sync") or {"status": "never"},
        "version": b.get("version", 0),
    }


@router.get("")
async def get_business(business: BusinessDep) -> dict:
    return ok(_public_business(business))


@router.patch("", dependencies=[CsrfDep])
async def patch_business(
    payload: BusinessPatch, business: BusinessDep, db: DbDep, admin: AdminDep
) -> dict:
    fields = payload.model_dump(exclude_none=True)
    if "business_hours" in fields:
        fields["business_hours"] = fields["business_hours"].model_dump()
    if "faqs" in fields:
        fields["faqs"] = [f.model_dump() for f in payload.faqs or []]
    # Only allow safe fields.
    fields = {k: v for k, v in fields.items() if k in _SAFE_FIELDS}
    if not fields:
        raise ValidationError("No updatable fields provided")

    bump = any(
        k in fields
        for k in ("business_hours", "timezone", "booking_horizon_days", "slot_increment_minutes")
    )
    await BusinessRepo(db).update(business["_id"], fields, bump_schedule=bump)
    await AuditRepo(db).record(
        {
            "business_id": business["_id"],
            "actor": f"admin:{admin['_id']}",
            "action": "business.updated",
            "target_type": "business",
            "target_id": business["_id"],
            "summary": {"fields": sorted(fields.keys())},
            "created_at": now_utc(),
        }
    )
    updated = await BusinessRepo(db).by_id(business["_id"])
    if updated is None:
        raise NotFoundError("Business not found")
    return ok(_public_business(updated))


@router.patch("/voice", dependencies=[CsrfDep])
async def patch_voice(
    payload: VoicePatch, business: BusinessDep, db: DbDep, admin: AdminDep
) -> dict:
    fields = payload.model_dump(exclude_none=True)
    update: dict = {}
    if "greeting" in fields:
        update["greeting"] = fields["greeting"]
    if "consent_disclosure" in fields:
        update["consent_disclosure"] = fields["consent_disclosure"]
    voice = dict(business.get("voice") or {})
    if "voice_id" in fields:
        voice["voice_id"] = fields["voice_id"]
    if "voice_provider" in fields:
        voice["provider"] = fields["voice_provider"]
    if voice:
        update["voice"] = voice
    if not update:
        raise ValidationError("No updatable fields provided")

    await BusinessRepo(db).update(business["_id"], update)
    await BusinessRepo(db).set_voice_sync(business["_id"], "pending")
    await job_svc.enqueue(
        db, job_svc.JOB_VOICE_SYNC, {"business_id": business["_id"]}, business_id=business["_id"]
    )
    await AuditRepo(db).record(
        {
            "business_id": business["_id"],
            "actor": f"admin:{admin['_id']}",
            "action": "business.voice_updated",
            "target_type": "business",
            "target_id": business["_id"],
            "summary": {"fields": sorted(update.keys())},
            "created_at": now_utc(),
        }
    )
    updated = await BusinessRepo(db).by_id(business["_id"])
    if updated is None:
        raise NotFoundError("Business not found")
    return ok(_public_business(updated))
