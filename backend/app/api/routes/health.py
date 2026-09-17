"""Health endpoints. /live checks process health; /ready checks real deps."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.deps import DbDep
from app.db.client import ping
from app.schemas.common import ok

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live() -> dict:
    return ok({"status": "live"})


@router.get("/health/ready")
async def ready(request: Request, db: DbDep) -> dict:
    checks = {"database": await ping(db)}

    # Tenant-to-Vapi mapping sanity (no secrets exposed).
    mapping = await db["businesses"].find_one(
        {"active": True, "vapi_phone_number_id": {"$exists": True, "$ne": None}}
    )
    checks["tenant_mapping"] = mapping is not None

    # Worker freshness: heartbeat or job activity within 10 min.
    from datetime import timedelta

    from app.services.timeutil import now_utc

    cutoff = now_utc() - timedelta(minutes=10)
    heartbeat = await db["meta"].find_one({"_id": "last_worker_heartbeat"})
    fresh_job = await db["jobs"].find_one({"updated_at": {"$gte": cutoff}})
    checks["worker"] = (
        heartbeat is not None and heartbeat.get("at") and heartbeat["at"] >= cutoff
    ) or fresh_job is not None

    degraded = [k for k, v in checks.items() if not v]
    status = "ready" if not degraded else ("degraded" if checks["database"] else "down")
    return ok({"status": status, "checks": checks, "degraded": degraded})
