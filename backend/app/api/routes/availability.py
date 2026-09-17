"""Availability admin routes: rules, exceptions, computed view."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Query

from app.api.deps import AdminDep, BusinessDep, CsrfDep, DbDep
from app.core import ids
from app.core.errors import NotFoundError, ValidationError
from app.repositories.availability_repo import (
    AvailabilityExceptionRepo,
    AvailabilityRuleRepo,
)
from app.repositories.business_repo import BusinessRepo
from app.repositories.catalog_repo import ProviderRepo
from app.repositories.clinical_repo import AppointmentRepo
from app.repositories.system_repo import AuditRepo
from app.schemas.admin import (
    AvailabilityExceptionCreate,
    AvailabilityRuleCreate,
    AvailabilityRulePatch,
)
from app.schemas.common import ok
from app.services import availability as avail
from app.services.timeutil import now_utc

router = APIRouter(prefix="/availability", tags=["availability"])


@router.get("")
async def get_availability(
    business: BusinessDep,
    db: DbDep,
    from_date: str = Query(alias="from"),
    to: str | None = None,
    provider_id: str | None = None,
) -> dict:
    try:
        start = date.fromisoformat(from_date)
        end = date.fromisoformat(to) if to else start + timedelta(days=7)
    except ValueError as exc:
        raise ValidationError("Invalid date range") from exc
    if (end - start).days > 62:
        raise ValidationError("Date range too large (max 62 days)")

    providers = await ProviderRepo(db).list(business["_id"], active_only=True)
    if provider_id:
        providers = [p for p in providers if p["_id"] == provider_id]
    rule_repo = AvailabilityRuleRepo(db)
    exc_repo = AvailabilityExceptionRepo(db)
    appt_repo = AppointmentRepo(db)

    days = []
    d = start
    while d <= end:
        day_providers = []
        for p in providers:
            rules = await rule_repo.list_for_provider(business["_id"], p["_id"])
            exceptions = await exc_repo.list_for_provider_date(
                business["_id"], p["_id"], d.isoformat()
            )
            windows = avail.effective_local_windows(
                business=business, rules=rules, exceptions=exceptions, local_date=d
            )
            utc_windows = avail.windows_to_utc(windows, d, business["timezone"])
            day_appts = await appt_repo.provider_day_confirmed(
                business["_id"], p["_id"],
                avail.local_to_utc(d, "00:00", business["timezone"]),
                avail.local_to_utc(d, "00:00", business["timezone"]) + timedelta(hours=48),
            )
            day_providers.append(
                {
                    "provider_id": p["_id"],
                    "provider_name": p["name"],
                    "windows": [
                        {"start": w.start.isoformat(), "end": w.end.isoformat()}
                        for w in utc_windows
                    ],
                    "booked": [
                        {
                            "id": a["_id"],
                            "start_at": a["start_at"].isoformat(),
                            "end_at": a["end_at"].isoformat(),
                            "service_id": a.get("service_id"),
                            "patient_name": a.get("patient_name"),
                        }
                        for a in day_appts
                    ],
                }
            )
        days.append({"local_date": d.isoformat(), "providers": day_providers})
        d += timedelta(days=1)
    return ok({"timezone": business["timezone"], "days": days})


@router.post("/rules", dependencies=[CsrfDep], status_code=201)
async def create_rule(
    payload: AvailabilityRuleCreate, business: BusinessDep, db: DbDep, admin: AdminDep
) -> dict:
    if payload.start_local >= payload.end_local:
        raise ValidationError("start_local must be before end_local")
    provider = await ProviderRepo(db).by_id(business["_id"], payload.provider_id)
    if provider is None:
        raise ValidationError("Unknown provider_id")
    doc = {
        "_id": ids.rule_id(),
        "business_id": business["_id"],
        **payload.model_dump(),
        "created_at": now_utc(),
        "updated_at": now_utc(),
    }
    await AvailabilityRuleRepo(db).insert(doc)
    await _bump_and_audit(db, business["_id"], admin, "availability.rule_created", doc["_id"])
    return ok({"id": doc["_id"], **payload.model_dump()})


@router.patch("/rules/{rule_id}", dependencies=[CsrfDep])
async def patch_rule(
    rule_id: str, payload: AvailabilityRulePatch, business: BusinessDep, db: DbDep, admin: AdminDep
) -> dict:
    fields = payload.model_dump(exclude_none=True)
    if not fields:
        raise ValidationError("No updatable fields provided")
    updated = await AvailabilityRuleRepo(db).patch(business["_id"], rule_id, fields)
    if updated is None:
        raise NotFoundError("Rule not found")
    await _bump_and_audit(db, business["_id"], admin, "availability.rule_updated", rule_id)
    return ok({"id": rule_id, **{k: updated.get(k) for k in fields}})


@router.post("/exceptions", dependencies=[CsrfDep], status_code=201)
async def create_exception(
    payload: AvailabilityExceptionCreate, business: BusinessDep, db: DbDep, admin: AdminDep
) -> dict:
    if payload.provider_id:
        provider = await ProviderRepo(db).by_id(business["_id"], payload.provider_id)
        if provider is None:
            raise ValidationError("Unknown provider_id")
    if payload.kind == "added" and (not payload.start_local or not payload.end_local):
        raise ValidationError("'added' exceptions require start_local and end_local")
    doc = {
        "_id": ids.exception_id(),
        "business_id": business["_id"],
        **payload.model_dump(),
        "active": True,
        "created_at": now_utc(),
        "updated_at": now_utc(),
    }
    await AvailabilityExceptionRepo(db).insert(doc)
    await _bump_and_audit(db, business["_id"], admin, "availability.exception_created", doc["_id"])
    return ok({"id": doc["_id"], **payload.model_dump()})


@router.delete("/exceptions/{exception_id}", dependencies=[CsrfDep])
async def delete_exception(
    exception_id: str, business: BusinessDep, db: DbDep, admin: AdminDep
) -> dict:
    deleted = await AvailabilityExceptionRepo(db).delete(business["_id"], exception_id)
    if not deleted:
        raise NotFoundError("Exception not found")
    await _bump_and_audit(
        db, business["_id"], admin, "availability.exception_deleted", exception_id
    )
    return ok({"deleted": True})


async def _bump_and_audit(db, business_id, admin, action, target_id) -> None:
    # Availability edits advance the schedule revision, expiring offers.
    await BusinessRepo(db).update(business_id, {}, bump_schedule=True)
    await AuditRepo(db).record(
        {
            "business_id": business_id,
            "actor": f"admin:{admin['_id']}",
            "action": action,
            "target_type": "availability",
            "target_id": target_id,
            "summary": {},
            "created_at": now_utc(),
        }
    )
