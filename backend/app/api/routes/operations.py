"""Patients, appointments, calls, and dashboard routes."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query

from app.api.deps import AdminDep, BusinessDep, CsrfDep, DbDep
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.security import phone_suffix
from app.repositories.clinical_repo import AppointmentRepo, CallRepo, PatientRepo
from app.repositories.system_repo import AuditRepo, MutationRepo
from app.schemas.admin import AppointmentStatusPatch
from app.schemas.common import AppointmentStatus, ok, ok_page
from app.services import dashboard as dash_svc
from app.services.timeutil import now_utc

patients_router = APIRouter(prefix="/patients", tags=["patients"])
appointments_router = APIRouter(prefix="/appointments", tags=["appointments"])
calls_router = APIRouter(prefix="/calls", tags=["calls"])
dashboard_router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _page_limit(limit: int | None) -> int:
    n = limit or 25
    return max(1, min(n, 100))


def _patient_view(p: dict) -> dict:
    return {
        "id": p["_id"],
        "display_name": p.get("display_name"),
        "phone": p.get("phone"),
        "phone_suffix": phone_suffix(p.get("phone")),
        "email": p.get("email"),
        "created_at": (p.get("created_at") or now_utc()).isoformat(),
    }


def _appt_view(a: dict) -> dict:
    return {
        "id": a["_id"],
        "patient_id": a.get("patient_id"),
        "patient_name": a.get("patient_name"),
        "phone_suffix": phone_suffix(a.get("patient_phone")),
        "provider_id": a.get("provider_id"),
        "service_id": a.get("service_id"),
        "call_id": a.get("call_id"),
        "start_at": a["start_at"].isoformat(),
        "end_at": a["end_at"].isoformat(),
        "timezone": a.get("timezone"),
        "status": a.get("status"),
        "source": a.get("source"),
        "created_at": a["created_at"].isoformat() if a.get("created_at") else None,
    }


def _call_view(c: dict, *, include_transcript: bool = False) -> dict:
    out = {
        "id": c["_id"],
        "vapi_call_id": c.get("vapi_call_id"),
        "phone_suffix": phone_suffix(c.get("caller_phone")),
        "patient_id": c.get("patient_id"),
        "appointment_id": c.get("appointment_id"),
        "started_at": c.get("started_at"),
        "ended_at": c.get("ended_at"),
        "duration_seconds": c.get("duration_seconds"),
        "outcome": c.get("outcome", "unknown"),
        "summary": c.get("summary"),
        "summary_status": c.get("summary_status", "none"),
        "transcript_status": c.get("transcript_status", "none"),
        "ended_reason": c.get("ended_reason"),
        "created_at": c["created_at"].isoformat() if c.get("created_at") else None,
    }
    if include_transcript:
        # Rendered as text only; never raw HTML. Expired content is gone.
        out["transcript"] = c.get("transcript")
    return out


@patients_router.get("")
async def list_patients(
    business: BusinessDep,
    db: DbDep,
    cursor: str | None = None,
    search: str | None = None,
    limit: int = 25,
) -> dict:
    items, nxt = await PatientRepo(db).list(
        business["_id"], cursor=cursor, search=search, limit=_page_limit(limit)
    )
    return ok_page([_patient_view(p) for p in items], nxt)


@patients_router.get("/{patient_id}")
async def get_patient(patient_id: str, business: BusinessDep, db: DbDep) -> dict:
    patient = await PatientRepo(db).by_id(business["_id"], patient_id)
    if patient is None:
        raise NotFoundError("Patient not found")
    appts, _ = await AppointmentRepo(db).list(
        business["_id"], cursor=None, limit=50
    )
    appts = [a for a in appts if a.get("patient_id") == patient_id]
    return ok({**_patient_view(patient), "appointments": [_appt_view(a) for a in appts]})


@appointments_router.get("")
async def list_appointments(
    business: BusinessDep,
    db: DbDep,
    cursor: str | None = None,
    status: str | None = None,
    provider_id: str | None = None,
    service_id: str | None = None,
    from_dt: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    limit: int = 25,
) -> dict:
    f = _parse_dt(from_dt)
    t = _parse_dt(to)
    items, nxt = await AppointmentRepo(db).list(
        business["_id"],
        cursor=cursor,
        limit=_page_limit(limit),
        status=status,
        provider_id=provider_id,
        service_id=service_id,
        from_dt=f,
        to_dt=t,
    )
    return ok_page([_appt_view(a) for a in items], nxt)


@appointments_router.get("/{appointment_id}")
async def get_appointment(appointment_id: str, business: BusinessDep, db: DbDep) -> dict:
    appt = await AppointmentRepo(db).by_id(business["_id"], appointment_id)
    if appt is None:
        raise NotFoundError("Appointment not found")
    call = None
    if appt.get("call_id"):
        call = await CallRepo(db).by_id(business["_id"], appt["call_id"])
    patient = None
    if appt.get("patient_id"):
        patient = await PatientRepo(db).by_id(business["_id"], appt["patient_id"])
    return ok(
        {
            **_appt_view(appt),
            "call": _call_view(call) if call else None,
            "patient": _patient_view(patient) if patient else None,
        }
    )


@appointments_router.patch("/{appointment_id}/status", dependencies=[CsrfDep])
async def patch_appointment_status(
    appointment_id: str,
    payload: AppointmentStatusPatch,
    business: BusinessDep,
    db: DbDep,
    admin: AdminDep,
) -> dict:
    mutations = MutationRepo(db)
    prior = await mutations.get(business["_id"], payload.idempotency_key)
    if prior is not None:
        return ok(prior["result"])

    repo = AppointmentRepo(db)
    appt = await repo.by_id(business["_id"], appointment_id)
    if appt is None:
        raise NotFoundError("Appointment not found")

    target = payload.status
    if not AppointmentStatus.can_transition(appt["status"], target):
        raise ConflictError(f"Cannot move appointment from {appt['status']} to {target}")
    if (
        target == "completed"
        and appt["start_at"] > now_utc()
        and not payload.allow_early_completion
    ):
        raise ConflictError(
            "Appointment cannot be completed before its start without an override"
        )

    res = await repo.update_status(
        business["_id"],
        appointment_id,
        appt["status"],
        target,
        extra={"status_reason": payload.reason, "status_changed_by": admin["_id"]},
    )
    if res.modified_count != 1:
        raise ConflictError("Appointment status changed concurrently")

    await AuditRepo(db).record(
        {
            "business_id": business["_id"],
            "actor": f"admin:{admin['_id']}",
            "action": f"appointment.{target}",
            "target_type": "appointment",
            "target_id": appointment_id,
            "summary": {"from": appt["status"], "to": target, "reason": payload.reason},
            "created_at": now_utc(),
        }
    )
    updated = await repo.by_id(business["_id"], appointment_id)
    if updated is None:
        raise NotFoundError("Appointment not found")
    result = _appt_view(updated)
    await mutations.insert(
        {
            "business_id": business["_id"],
            "key": payload.idempotency_key,
            "result": result,
            "created_at": now_utc(),
        }
    )
    return ok(result)


@calls_router.get("")
async def list_calls(
    business: BusinessDep,
    db: DbDep,
    cursor: str | None = None,
    outcome: str | None = None,
    limit: int = 25,
) -> dict:
    items, nxt = await CallRepo(db).list(
        business["_id"], cursor=cursor, limit=_page_limit(limit), outcome=outcome
    )
    return ok_page([_call_view(c) for c in items], nxt)


@calls_router.get("/{call_id}")
async def get_call(call_id: str, business: BusinessDep, db: DbDep) -> dict:
    call = await CallRepo(db).by_id(business["_id"], call_id)
    if call is None:
        raise NotFoundError("Call not found")
    appt = None
    if call.get("appointment_id"):
        appt = await AppointmentRepo(db).by_id(business["_id"], call["appointment_id"])
    return ok(
        {
            **_call_view(call, include_transcript=True),
            "appointment": _appt_view(appt) if appt else None,
        }
    )


@dashboard_router.get("/summary")
async def dashboard_summary(
    business: BusinessDep, db: DbDep, date: str | None = None
) -> dict:
    return ok(await dash_svc.dashboard_summary(db, business, date))


@dashboard_router.get("/activity")
async def dashboard_activity(
    business: BusinessDep, db: DbDep, cursor: str | None = None, limit: int = 25
) -> dict:
    items, nxt = await dash_svc.activity_feed(
        db, business["_id"], cursor=cursor, limit=_page_limit(limit)
    )
    return ok_page(
        [
            {
                "id": i["_id"],
                "actor": i.get("actor"),
                "action": i.get("action"),
                "target_id": i.get("target_id"),
                "summary": i.get("summary"),
                "created_at": i["created_at"].isoformat() if i.get("created_at") else None,
            }
            for i in items
        ],
        nxt,
    )


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError("Invalid datetime") from exc
