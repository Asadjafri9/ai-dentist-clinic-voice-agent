"""Business (tenant) repository."""

from __future__ import annotations

from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from pymongo.results import UpdateResult

from app.services.timeutil import now_utc


class BusinessRepo:
    def __init__(self, db: AsyncDatabase) -> None:  # type: ignore[type-arg]
        self.col = db["businesses"]

    async def by_id(self, business_id: str) -> dict[str, Any] | None:
        return await self.col.find_one({"_id": business_id})

    async def by_slug(self, slug: str) -> dict[str, Any] | None:
        return await self.col.find_one({"slug": slug})

    async def by_vapi_phone_number_id(self, phone_number_id: str) -> dict[str, Any] | None:
        return await self.col.find_one({"vapi_phone_number_id": phone_number_id})

    async def by_vapi_assistant_id(self, assistant_id: str) -> dict[str, Any] | None:
        return await self.col.find_one({"vapi_assistant_id": assistant_id})

    async def update(
        self, business_id: str, fields: dict[str, Any], *, bump_schedule: bool = False
    ) -> UpdateResult:
        update: dict[str, Any] = {
            "$set": {**fields, "updated_at": now_utc()},
        }
        if bump_schedule:
            update["$inc"] = {"schedule_version": 1}
        return await self.col.update_one({"_id": business_id}, update)

    async def set_voice_sync(
        self,
        business_id: str,
        status: str,
        *,
        synced_at=None,
        error: str | None = None,
        assistant_version: str | None = None,
    ) -> None:
        fields: dict[str, Any] = {
            "voice_sync.status": status,
            "voice_sync.error": error,
            "updated_at": now_utc(),
        }
        if synced_at is not None:
            fields["voice_sync.last_synced_at"] = synced_at
        if assistant_version is not None:
            fields["voice_sync.assistant_version"] = assistant_version
        await self.col.update_one({"_id": business_id}, {"$set": fields})
