"""Service and provider admin routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import AdminDep, BusinessDep, CsrfDep, DbDep
from app.core import ids
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.repositories.catalog_repo import ProviderRepo, ServiceRepo
from app.repositories.clinical_repo import AppointmentRepo
from app.repositories.system_repo import AuditRepo
from app.schemas.admin import (
    ProviderCreate,
    ProviderPatch,
    ServiceCreate,
    ServicePatch,
)
from app.schemas.common import ok
from app.services.timeutil import now_utc

services_router = APIRouter(prefix="/services", tags=["services"])
providers_router = APIRouter(prefix="/providers", tags=["providers"])


def _service_view(s: dict) -> dict:
    return {
        "id": s["_id"],
        "slug": s["slug"],
        "display_name": s["display_name"],
        "description": s.get("description"),
        "aliases": s.get("aliases") or [],
        "duration_minutes": s["duration_minutes"],
        "buffer_before_minutes": s.get("buffer_before_minutes", 0),
        "buffer_after_minutes": s.get("buffer_after_minutes", 0),
        "active": s.get("active", True),
        "voice_bookable": s.get("voice_bookable", True),
        "version": s.get("version", 0),
    }


def _provider_view(p: dict) -> dict:
    return {
        "id": p["_id"],
        "name": p["name"],
        "title": p.get("title"),
        "service_ids": p.get("service_ids") or [],
        "active": p.get("active", True),
        "version": p.get("version", 0),
    }


@services_router.get("")
async def list_services(business: BusinessDep, db: DbDep) -> dict:
    items = await ServiceRepo(db).list(business["_id"])
    return ok({"items": [_service_view(s) for s in items]})


@services_router.post("", dependencies=[CsrfDep], status_code=201)
async def create_service(
    payload: ServiceCreate, business: BusinessDep, db: DbDep, admin: AdminDep
) -> dict:
    repo = ServiceRepo(db)
    if await repo.by_slug(business["_id"], payload.slug):
        raise ConflictError("A service with that slug already exists")
    doc = {
        "_id": ids.service_id(),
        "business_id": business["_id"],
        **payload.model_dump(),
        "version": 0,
        "created_at": now_utc(),
        "updated_at": now_utc(),
    }
    await repo.insert(doc)
    await _audit(db, business["_id"], admin, "service.created", doc["_id"], {"slug": doc["slug"]})
    return ok(_service_view(doc))


@services_router.patch("/{service_id}", dependencies=[CsrfDep])
async def patch_service(
    service_id: str, payload: ServicePatch, business: BusinessDep, db: DbDep, admin: AdminDep
) -> dict:
    fields = payload.model_dump(exclude_none=True)
    version = fields.pop("version", None)
    if not fields:
        raise ValidationError("No updatable fields provided")

    repo = ServiceRepo(db)
    existing = await repo.by_id(business["_id"], service_id)
    if existing is None:
        raise NotFoundError("Service not found")

    # Prevent deactivation when future confirmed appointments reference it.
    if fields.get("active") is False:
        count = await AppointmentRepo(db).count_future_for_service(business["_id"], service_id)
        if count:
            raise ConflictError(
                f"{count} future confirmed appointment(s) reference this service; "
                "it cannot be deactivated until they resolve."
            )

    updated = await repo.patch(business["_id"], service_id, fields, version)
    if updated is None:
        raise ConflictError("Service was modified concurrently; reload and retry")
    await _audit(
        db, business["_id"], admin, "service.updated", service_id, {"fields": sorted(fields)}
    )
    return ok(_service_view(updated))


@providers_router.get("")
async def list_providers(business: BusinessDep, db: DbDep) -> dict:
    items = await ProviderRepo(db).list(business["_id"])
    return ok({"items": [_provider_view(p) for p in items]})


@providers_router.post("", dependencies=[CsrfDep], status_code=201)
async def create_provider(
    payload: ProviderCreate, business: BusinessDep, db: DbDep, admin: AdminDep
) -> dict:
    service_repo = ServiceRepo(db)
    for sid in payload.service_ids:
        if not await service_repo.by_id(business["_id"], sid):
            raise ValidationError(f"Unknown service id: {sid}")
    doc = {
        "_id": ids.provider_id(),
        "business_id": business["_id"],
        **payload.model_dump(),
        "version": 0,
        "created_at": now_utc(),
        "updated_at": now_utc(),
    }
    await ProviderRepo(db).insert(doc)
    await _audit(db, business["_id"], admin, "provider.created", doc["_id"], {"name": doc["name"]})
    return ok(_provider_view(doc))


@providers_router.patch("/{provider_id}", dependencies=[CsrfDep])
async def patch_provider(
    provider_id: str, payload: ProviderPatch, business: BusinessDep, db: DbDep, admin: AdminDep
) -> dict:
    fields = payload.model_dump(exclude_none=True)
    version = fields.pop("version", None)
    if not fields:
        raise ValidationError("No updatable fields provided")

    repo = ProviderRepo(db)
    existing = await repo.by_id(business["_id"], provider_id)
    if existing is None:
        raise NotFoundError("Provider not found")

    if "service_ids" in fields:
        service_repo = ServiceRepo(db)
        for sid in fields["service_ids"]:
            if not await service_repo.by_id(business["_id"], sid):
                raise ValidationError(f"Unknown service id: {sid}")

    if fields.get("active") is False:
        count = await AppointmentRepo(db).count_future_for_provider(
            business["_id"], provider_id
        )
        if count:
            raise ConflictError(
                f"{count} future confirmed appointment(s) reference this provider; "
                "it cannot be deactivated until they resolve."
            )

    updated = await repo.patch(business["_id"], provider_id, fields, version)
    if updated is None:
        raise ConflictError("Provider was modified concurrently; reload and retry")
    await _audit(
        db, business["_id"], admin, "provider.updated", provider_id, {"fields": sorted(fields)}
    )
    return ok(_provider_view(updated))


async def _audit(db, business_id, admin, action, target_id, summary) -> None:
    await AuditRepo(db).record(
        {
            "business_id": business_id,
            "actor": f"admin:{admin['_id']}",
            "action": action,
            "target_type": action.split(".")[0],
            "target_id": target_id,
            "summary": summary,
            "created_at": now_utc(),
        }
    )
