"""Service and provider repositories. Every query is tenant-scoped."""

from __future__ import annotations

import builtins
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from app.services.timeutil import now_utc


class ServiceRepo:
    def __init__(self, db: AsyncDatabase) -> None:  # type: ignore[type-arg]
        self.col = db["services"]

    async def by_id(self, business_id: str, service_id: str) -> dict[str, Any] | None:
        return await self.col.find_one({"_id": service_id, "business_id": business_id})

    async def by_slug(self, business_id: str, slug: str) -> dict[str, Any] | None:
        return await self.col.find_one({"business_id": business_id, "slug": slug})

    async def list(self, business_id: str, *, active_only: bool = False) -> list[dict[str, Any]]:
        q: dict[str, Any] = {"business_id": business_id}
        if active_only:
            q["active"] = True
        return await self.col.find(q).sort("display_name", 1).to_list(None)

    async def list_voice_bookable(self, business_id: str) -> builtins.list[dict[str, Any]]:
        return (
            await self.col.find(
                {"business_id": business_id, "active": True, "voice_bookable": True}
            )
            .sort("display_name", 1)
            .to_list(None)
        )

    async def insert(self, doc: dict[str, Any]) -> None:
        await self.col.insert_one(doc)

    async def patch(
        self, business_id: str, service_id: str, fields: dict[str, Any], version: int | None
    ) -> dict[str, Any] | None:
        q: dict[str, Any] = {"_id": service_id, "business_id": business_id}
        if version is not None:
            q["version"] = version
        res = await self.col.find_one_and_update(
            q,
            {"$set": {**fields, "updated_at": now_utc()}, "$inc": {"version": 1}},
            return_document=True,
        )
        return res


class ProviderRepo:
    def __init__(self, db: AsyncDatabase) -> None:  # type: ignore[type-arg]
        self.col = db["providers"]

    async def by_id(self, business_id: str, provider_id: str) -> dict[str, Any] | None:
        return await self.col.find_one({"_id": provider_id, "business_id": business_id})

    async def list(self, business_id: str, *, active_only: bool = False) -> list[dict[str, Any]]:
        q: dict[str, Any] = {"business_id": business_id}
        if active_only:
            q["active"] = True
        return await self.col.find(q).sort("name", 1).to_list(None)

    async def insert(self, doc: dict[str, Any]) -> None:
        await self.col.insert_one(doc)

    async def patch(
        self, business_id: str, provider_id: str, fields: dict[str, Any], version: int | None
    ) -> dict[str, Any] | None:
        q: dict[str, Any] = {"_id": provider_id, "business_id": business_id}
        if version is not None:
            q["version"] = version
        return await self.col.find_one_and_update(
            q,
            {"$set": {**fields, "updated_at": now_utc()}, "$inc": {"version": 1}},
            return_document=True,
        )

    async def find_by_name(self, business_id: str, name: str) -> builtins.list[dict[str, Any]]:
        """Case-insensitive name resolution; may return multiple for ambiguity."""
        import re

        pattern = re.compile(f"^{re.escape(name.strip())}$", re.IGNORECASE)
        return await self.col.find(
            {"business_id": business_id, "active": True, "name": pattern}
        ).to_list(None)
