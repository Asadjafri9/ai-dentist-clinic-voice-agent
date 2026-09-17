"""Integration events, jobs, audit, tool results, and admin/session repos."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.services.timeutil import now_utc


class IntegrationEventRepo:
    def __init__(self, db: AsyncDatabase) -> None:  # type: ignore[type-arg]
        self.col = db["integration_events"]

    async def insert_inbox(self, doc: dict[str, Any]) -> bool:
        """Return False when the fingerprint already exists (duplicate)."""
        try:
            await self.col.insert_one(doc)
            return True
        except DuplicateKeyError:
            return False

    async def by_fingerprint(self, fingerprint: str) -> dict[str, Any] | None:
        return await self.col.find_one({"fingerprint": fingerprint})

    async def set_status(self, fingerprint: str, status: str, **fields: Any) -> None:
        await self.col.update_one(
            {"fingerprint": fingerprint},
            {"$set": {"status": status, **fields, "updated_at": now_utc()}},
        )


class JobRepo:
    def __init__(self, db: AsyncDatabase) -> None:  # type: ignore[type-arg]
        self.col = db["jobs"]

    async def enqueue(
        self,
        job: dict[str, Any],
        session=None,
    ) -> None:
        await self.col.insert_one(job, session=session)

    async def claim(self, worker_id: str, lease_seconds: int) -> dict[str, Any] | None:
        now = now_utc()
        return await self.col.find_one_and_update(
            {
                "status": "pending",
                "available_at": {"$lte": now},
            },
            {
                "$set": {
                    "status": "processing",
                    "lease_owner": worker_id,
                    "lease_expires_at": now + timedelta(seconds=lease_seconds),
                    "claimed_at": now,
                },
                "$inc": {"attempts": 1},
            },
            sort=[("available_at", 1)],
        )

    async def complete(self, job_id: str) -> None:
        await self.col.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": "done",
                    "completed_at": now_utc(),
                    "updated_at": now_utc(),
                }
            },
        )

    async def reschedule(self, job_id: str, delay_seconds: float, error_code: str) -> None:
        await self.col.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": "pending",
                    "available_at": now_utc() + timedelta(seconds=delay_seconds),
                    "last_error_code": error_code,
                    "lease_owner": None,
                    "lease_expires_at": None,
                    "updated_at": now_utc(),
                }
            },
        )

    async def dead_letter(self, job_id: str, error_code: str) -> None:
        await self.col.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": "dead",
                    "last_error_code": error_code,
                    "lease_owner": None,
                    "lease_expires_at": None,
                    "updated_at": now_utc(),
                }
            },
        )

    async def requeue_expired_leases(self) -> int:
        now = now_utc()
        res = await self.col.update_many(
            {"status": "processing", "lease_expires_at": {"$lt": now}},
            {
                "$set": {
                    "status": "pending",
                    "lease_owner": None,
                    "lease_expires_at": None,
                    "updated_at": now,
                }
            },
        )
        return res.modified_count

    async def lag_seconds(self) -> float:
        doc = await self.col.find_one(
            {"status": "pending"}, sort=[("available_at", 1)]
        )
        if not doc:
            return 0.0
        return max(0.0, (now_utc() - doc["available_at"]).total_seconds())


class AuditRepo:
    def __init__(self, db: AsyncDatabase) -> None:  # type: ignore[type-arg]
        self.col = db["audit_events"]

    async def record(self, doc: dict[str, Any], session=None) -> None:
        await self.col.insert_one(doc, session=session)

    async def list(
        self, business_id: str, *, cursor: str | None, limit: int
    ) -> tuple[list[dict[str, Any]], str | None]:
        q: dict[str, Any] = {"business_id": business_id}
        if cursor:
            q["_id"] = {"$lt": cursor}
        items = (
            await self.col.find(q)
            .sort([("created_at", -1), ("_id", -1)])
            .limit(limit + 1)
            .to_list(None)
        )
        next_cursor = items[-1]["_id"] if len(items) > limit else None
        return items[:limit], next_cursor


class ToolResultRepo:
    """Idempotent tool-delivery records keyed by (business, call, tool_call)."""

    def __init__(self, db: AsyncDatabase) -> None:  # type: ignore[type-arg]
        self.col = db["tool_results"]

    async def get(self, business_id: str, call_id: str, tool_call_id: str) -> dict | None:
        return await self.col.find_one(
            {
                "business_id": business_id,
                "call_id": call_id,
                "tool_call_id": tool_call_id,
            }
        )

    async def insert(self, doc: dict[str, Any]) -> bool:
        try:
            await self.col.insert_one(doc)
            return True
        except DuplicateKeyError:
            return False


class MutationRepo:
    """Admin-mutation idempotency keys."""

    def __init__(self, db: AsyncDatabase) -> None:  # type: ignore[type-arg]
        self.col = db["admin_mutations"]

    async def get(self, business_id: str, key: str) -> dict | None:
        return await self.col.find_one({"business_id": business_id, "key": key})

    async def insert(self, doc: dict[str, Any]) -> bool:
        try:
            await self.col.insert_one(doc)
            return True
        except DuplicateKeyError:
            return False


class AdminUserRepo:
    def __init__(self, db: AsyncDatabase) -> None:  # type: ignore[type-arg]
        self.col = db["admin_users"]

    async def by_email(self, email: str) -> dict[str, Any] | None:
        return await self.col.find_one({"email": email.lower().strip()})

    async def by_id(self, admin_id: str) -> dict[str, Any] | None:
        return await self.col.find_one({"_id": admin_id})

    async def insert(self, doc: dict[str, Any]) -> None:
        await self.col.insert_one(doc)

    async def touch_login(self, admin_id: str) -> None:
        await self.col.update_one(
            {"_id": admin_id}, {"$set": {"last_login_at": now_utc()}}
        )


class SessionRepo:
    def __init__(self, db: AsyncDatabase) -> None:  # type: ignore[type-arg]
        self.col = db["sessions"]

    async def create(self, doc: dict[str, Any]) -> None:
        await self.col.insert_one(doc)

    async def by_token_hash(self, token_hash: str) -> dict[str, Any] | None:
        return await self.col.find_one({"token_hash": token_hash})

    async def revoke(self, session_id: str) -> None:
        await self.col.update_one(
            {"_id": session_id},
            {"$set": {"revoked_at": now_utc()}},
        )

    async def revoke_all_for_admin(self, admin_id: str) -> None:
        await self.col.update_many(
            {"admin_id": admin_id, "revoked_at": None},
            {"$set": {"revoked_at": now_utc()}},
        )
