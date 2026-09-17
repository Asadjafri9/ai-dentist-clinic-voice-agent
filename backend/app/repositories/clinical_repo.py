"""Patient, appointment, and call repositories."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.results import UpdateResult

from app.services.timeutil import now_utc


class PatientRepo:
    def __init__(self, db: AsyncDatabase) -> None:  # type: ignore[type-arg]
        self.col = db["patients"]

    async def by_id(self, business_id: str, patient_id: str) -> dict[str, Any] | None:
        return await self.col.find_one({"_id": patient_id, "business_id": business_id})

    async def by_phone(self, business_id: str, phone: str) -> dict[str, Any] | None:
        return await self.col.find_one({"business_id": business_id, "phone": phone})

    async def upsert_by_phone(
        self,
        business_id: str,
        phone: str,
        display_name: str,
        patient_id: str,
        session: AsyncClientSession | None = None,
    ) -> dict[str, Any]:
        """Upsert patient keyed on normalized phone.

        Name update rule (deterministic): an existing patient's stored
        display name is never overwritten by a later call; the
        call-supplied name lives on the appointment snapshot. Set
        display name only on first insert.
        """
        now = now_utc()
        await self.col.update_one(
            {"business_id": business_id, "phone": phone},
            {
                "$setOnInsert": {
                    "_id": patient_id,
                    "business_id": business_id,
                    "phone": phone,
                    "display_name": display_name,
                    "created_at": now,
                },
                "$set": {"updated_at": now},
            },
            upsert=True,
            session=session,
        )
        doc = await self.col.find_one(
            {"business_id": business_id, "phone": phone}, session=session
        )
        assert doc is not None
        return doc

    async def list(
        self, business_id: str, *, cursor: str | None, search: str | None, limit: int
    ) -> tuple[list[dict[str, Any]], str | None]:
        import re

        q: dict[str, Any] = {"business_id": business_id}
        if search:
            pattern = re.compile(re.escape(search), re.IGNORECASE)
            q["$or"] = [{"display_name": pattern}, {"phone": {"$regex": re.escape(search)}}]
        if cursor:
            q["_id"] = {"$gt": cursor}
        items = await self.col.find(q).sort("_id", 1).limit(limit + 1).to_list(None)
        next_cursor = items[-1]["_id"] if len(items) > limit else None
        return items[:limit], next_cursor


class AppointmentRepo:
    def __init__(self, db: AsyncDatabase) -> None:  # type: ignore[type-arg]
        self.col = db["appointments"]

    async def by_id(self, business_id: str, appointment_id: str) -> dict[str, Any] | None:
        return await self.col.find_one({"_id": appointment_id, "business_id": business_id})

    async def by_booking_intent(
        self, business_id: str, booking_intent_id: str, session: AsyncClientSession | None = None
    ) -> dict[str, Any] | None:
        return await self.col.find_one(
            {"business_id": business_id, "booking_intent_id": booking_intent_id},
            session=session,
        )

    async def overlapping(
        self,
        business_id: str,
        provider_id: str,
        start_at: datetime,
        end_at: datetime,
        session: AsyncClientSession | None = None,
    ) -> list[dict[str, Any]]:
        return await self.col.find(
            {
                "business_id": business_id,
                "provider_id": provider_id,
                "status": "confirmed",
                "start_at": {"$lt": end_at},
                "end_at": {"$gt": start_at},
            },
            session=session,
        ).to_list(None)

    async def provider_day_confirmed(
        self,
        business_id: str,
        provider_id: str,
        day_start_utc: datetime,
        day_end_utc: datetime,
        session: AsyncClientSession | None = None,
    ) -> list[dict[str, Any]]:
        return await self.col.find(
            {
                "business_id": business_id,
                "provider_id": provider_id,
                "status": "confirmed",
                "start_at": {"$lt": day_end_utc},
                "end_at": {"$gt": day_start_utc},
            },
            session=session,
        ).to_list(None)

    async def insert(self, doc: dict[str, Any], session: AsyncClientSession | None = None) -> None:
        await self.col.insert_one(doc, session=session)

    async def update_status(
        self,
        business_id: str,
        appointment_id: str,
        from_status: str,
        to_status: str,
        extra: dict[str, Any] | None = None,
        session: AsyncClientSession | None = None,
    ) -> UpdateResult:
        return await self.col.update_one(
            {"_id": appointment_id, "business_id": business_id, "status": from_status},
            {
                "$set": {
                    "status": to_status,
                    "updated_at": now_utc(),
                    **(extra or {}),
                }
            },
            session=session,
        )

    async def link_call(
        self, business_id: str, appointment_id: str, call_id: str
    ) -> None:
        await self.col.update_one(
            {"_id": appointment_id, "business_id": business_id},
            {"$set": {"call_id": call_id}},
        )

    async def list(
        self,
        business_id: str,
        *,
        cursor: str | None,
        limit: int,
        status: str | None = None,
        provider_id: str | None = None,
        service_id: str | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        q: dict[str, Any] = {"business_id": business_id}
        if status:
            q["status"] = status
        if provider_id:
            q["provider_id"] = provider_id
        if service_id:
            q["service_id"] = service_id
        if from_dt or to_dt:
            rng: dict[str, Any] = {}
            if from_dt:
                rng["$gte"] = from_dt
            if to_dt:
                rng["$lte"] = to_dt
            q["start_at"] = rng
        if cursor:
            q["_id"] = {"$lt": cursor}
        items = (
            await self.col.find(q)
            .sort([("start_at", -1), ("_id", -1)])
            .limit(limit + 1)
            .to_list(None)
        )
        next_cursor = items[-1]["_id"] if len(items) > limit else None
        return items[:limit], next_cursor

    async def count_future_for_provider(self, business_id: str, provider_id: str) -> int:
        return await self.col.count_documents(
            {
                "business_id": business_id,
                "provider_id": provider_id,
                "status": "confirmed",
                "start_at": {"$gt": now_utc()},
            }
        )

    async def count_future_for_service(self, business_id: str, service_id: str) -> int:
        return await self.col.count_documents(
            {
                "business_id": business_id,
                "service_id": service_id,
                "status": "confirmed",
                "start_at": {"$gt": now_utc()},
            }
        )


class CallRepo:
    def __init__(self, db: AsyncDatabase) -> None:  # type: ignore[type-arg]
        self.col = db["calls"]

    async def by_id(self, business_id: str, call_id: str) -> dict[str, Any] | None:
        return await self.col.find_one({"_id": call_id, "business_id": business_id})

    async def by_vapi_call_id(
        self, business_id: str, vapi_call_id: str
    ) -> dict[str, Any] | None:
        return await self.col.find_one(
            {"business_id": business_id, "vapi_call_id": vapi_call_id}
        )

    async def upsert_in_progress(
        self, business_id: str, vapi_call_id: str, fields: dict[str, Any]
    ) -> dict[str, Any]:
        from app.core import ids

        now = now_utc()
        await self.col.update_one(
            {"business_id": business_id, "vapi_call_id": vapi_call_id},
            {
                "$setOnInsert": {
                    "_id": ids.call_id(),
                    "business_id": business_id,
                    "vapi_call_id": vapi_call_id,
                    "created_at": now,
                    "outcome": "unknown",
                    "tool_calls": [],
                },
                "$set": {**fields, "updated_at": now},
            },
            upsert=True,
        )
        doc = await self.by_vapi_call_id(business_id, vapi_call_id)
        assert doc is not None
        return doc

    async def update(self, business_id: str, call_id: str, fields: dict[str, Any]) -> None:
        await self.col.update_one(
            {"_id": call_id, "business_id": business_id},
            {"$set": {**fields, "updated_at": now_utc()}},
        )

    async def record_tool_call(
        self, business_id: str, call_id: str, tool_name: str
    ) -> None:
        await self.col.update_one(
            {"_id": call_id, "business_id": business_id},
            {
                "$addToSet": {"tool_calls": tool_name},
                "$set": {"updated_at": now_utc()},
            },
        )

    async def list(
        self,
        business_id: str,
        *,
        cursor: str | None,
        limit: int,
        outcome: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        q: dict[str, Any] = {"business_id": business_id}
        if outcome:
            q["outcome"] = outcome
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
