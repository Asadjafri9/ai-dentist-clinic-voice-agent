"""Durable job helpers. Sensitive payloads are referenced, not copied."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from app.core import ids
from app.repositories.system_repo import JobRepo
from app.services.timeutil import now_utc

JOB_PROCESS_CALL_EVENT = "process_call_event"
JOB_RETENTION_PURGE = "retention_purge"
JOB_VOICE_SYNC = "voice_config_sync"
JOB_DAILY_TICK = "daily_tick"

JOB_TTL_DAYS = 30


async def enqueue(
    db: AsyncDatabase,  # type: ignore[type-arg]
    job_type: str,
    payload: dict[str, Any],
    *,
    business_id: str | None = None,
    delay_seconds: float = 0,
    session=None,
) -> str:
    job = {
        "_id": ids.job_id(),
        "type": job_type,
        "business_id": business_id,
        "payload": payload,
        "status": "pending",
        "attempts": 0,
        "available_at": now_utc() + timedelta(seconds=delay_seconds),
        "lease_owner": None,
        "lease_expires_at": None,
        "last_error_code": None,
        "created_at": now_utc(),
        "updated_at": now_utc(),
        "expires_at": now_utc() + timedelta(days=JOB_TTL_DAYS),
    }
    await JobRepo(db).enqueue(job, session=session)
    return str(job["_id"])
