"""Opaque session management. Only the token hash is stored."""

from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from app.core import ids
from app.core.errors import UnauthorizedError
from app.core.security import constant_time_equals, hmac_sha256, sha256_hex
from app.repositories.system_repo import AdminUserRepo, SessionRepo
from app.services.timeutil import now_utc

CSRF_COOKIE = "ai_voice_csrf"


async def create_session(
    db: AsyncDatabase, admin_id: str, ttl_hours: int  # type: ignore[type-arg]
) -> tuple[str, dict[str, Any]]:
    token = ids.session_token()
    doc = {
        "_id": ids.new_id("ses"),
        "admin_id": admin_id,
        "token_hash": sha256_hex(token),
        "created_at": now_utc(),
        "expires_at": now_utc() + timedelta(hours=ttl_hours),
        "revoked_at": None,
    }
    await SessionRepo(db).create(doc)
    return token, doc


async def resolve_session(
    db: AsyncDatabase, token: str | None  # type: ignore[type-arg]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (session, admin). Raises UnauthorizedError."""
    if not token:
        raise UnauthorizedError()
    session = await SessionRepo(db).by_token_hash(sha256_hex(token))
    if (
        session is None
        or session.get("revoked_at") is not None
        or session["expires_at"] <= now_utc()
    ):
        raise UnauthorizedError()
    admin = await AdminUserRepo(db).by_id(session["admin_id"])
    if admin is None or not admin.get("active", True):
        raise UnauthorizedError()
    return session, admin


def mint_csrf(session_token_hash: str, secret: str) -> str:
    """CSRF token bound to the session: nonce.hmac."""
    nonce = secrets.token_urlsafe(16)
    sig = hmac_sha256(secret, f"{session_token_hash}:{nonce}".encode())
    return f"{nonce}.{sig}"


def verify_csrf(session_token_hash: str, secret: str, presented: str | None) -> bool:
    if not presented or "." not in presented:
        return False
    nonce, sig = presented.rsplit(".", 1)
    expected = hmac_sha256(secret, f"{session_token_hash}:{nonce}".encode())
    return constant_time_equals(expected, sig)
