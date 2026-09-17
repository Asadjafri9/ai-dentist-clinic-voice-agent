"""Availability rules, exceptions, and schedule-day guard repositories."""

from __future__ import annotations

from datetime import date
from typing import Any

from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.results import UpdateResult

from app.services.timeutil import now_utc


class AvailabilityRuleRepo:
    def __init__(self, db: AsyncDatabase) -> None:  # type: ignore[type-arg]
        self.col = db["availability_rules"]

    async def list_for_provider(
        self, business_id: str, provider_id: str
    ) -> list[dict[str, Any]]:
        return (
            await self.col.find({"business_id": business_id, "provider_id": provider_id})
            .sort("weekday", 1)
            .to_list(None)
        )

    async def list_for_business(self, business_id: str) -> list[dict[str, Any]]:
        return (
            await self.col.find({"business_id": business_id}).sort("weekday", 1).to_list(None)
        )

    async def insert(self, doc: dict[str, Any]) -> None:
        await self.col.insert_one(doc)

    async def patch(
        self, business_id: str, rule_id: str, fields: dict[str, Any]
    ) -> dict[str, Any] | None:
        return await self.col.find_one_and_update(
            {"_id": rule_id, "business_id": business_id},
            {"$set": {**fields, "updated_at": now_utc()}},
            return_document=True,
        )


class AvailabilityExceptionRepo:
    def __init__(self, db: AsyncDatabase) -> None:  # type: ignore[type-arg]
        self.col = db["availability_exceptions"]

    async def list_for_range(
        self, business_id: str, from_date: str, to_date: str
    ) -> list[dict[str, Any]]:
        return (
            await self.col.find(
                {
                    "business_id": business_id,
                    "local_date": {"$gte": from_date, "$lte": to_date},
                }
            )
            .sort("local_date", 1)
            .to_list(None)
        )

    async def list_for_provider_date(
        self, business_id: str, provider_id: str, local_date: str
    ) -> list[dict[str, Any]]:
        return await self.col.find(
            {
                "business_id": business_id,
                "local_date": local_date,
                "provider_id": {"$in": [provider_id, None]},
            }
        ).to_list(None)

    async def insert(self, doc: dict[str, Any]) -> None:
        await self.col.insert_one(doc)

    async def delete(self, business_id: str, exception_id: str) -> bool:
        res = await self.col.delete_one({"_id": exception_id, "business_id": business_id})
        return res.deleted_count == 1


class ScheduleDayRepo:
    """Optimistic concurrency guard: one doc per business/provider/local date."""

    def __init__(self, db: AsyncDatabase) -> None:  # type: ignore[type-arg]
        self.col = db["resource_schedule_days"]

    async def lock(
        self,
        business_id: str,
        provider_id: str,
        local_date: date,
        session: AsyncClientSession | None = None,
    ) -> UpdateResult:
        """Upsert + advance version. Concurrent txns contend on this doc."""
        return await self.col.update_one(
            {
                "business_id": business_id,
                "provider_id": provider_id,
                "local_date": local_date.isoformat(),
            },
            {
                "$inc": {"version": 1},
                "$set": {"updated_at": now_utc()},
                "$setOnInsert": {
                    "business_id": business_id,
                    "provider_id": provider_id,
                    "local_date": local_date.isoformat(),
                },
            },
            upsert=True,
            session=session,
        )
