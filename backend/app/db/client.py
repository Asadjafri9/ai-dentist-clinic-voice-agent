"""MongoDB async client lifecycle (PyMongo AsyncMongoClient)."""

from __future__ import annotations

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

_client: AsyncMongoClient | None = None  # type: ignore[type-arg]


def init_client(uri: str) -> AsyncMongoClient:  # type: ignore[type-arg]
    global _client
    _client = AsyncMongoClient(uri, appname="ai-dentist-voice-agent", tz_aware=True)
    return _client


def get_client() -> AsyncMongoClient:  # type: ignore[type-arg]
    if _client is None:
        raise RuntimeError("MongoDB client not initialized")
    return _client


def get_db(name: str) -> AsyncDatabase:  # type: ignore[type-arg]
    return get_client()[name]


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None


async def ping(db: AsyncDatabase) -> bool:  # type: ignore[type-arg]
    try:
        await db.command("ping")
        return True
    except Exception:
        return False
