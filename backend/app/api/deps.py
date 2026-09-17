"""FastAPI dependencies: db, settings, authenticated admin, CSRF."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Annotated, Any

from fastapi import Depends, Request
from pymongo.asynchronous.database import AsyncDatabase

from app.auth import sessions as session_svc
from app.auth.sessions import CSRF_COOKIE
from app.core.config import Settings, get_settings
from app.core.errors import ForbiddenError, RateLimitedError
from app.core.security import sha256_hex

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_db(request: Request) -> AsyncDatabase:  # type: ignore[type-arg]
    return request.app.state.db


DbDep = Annotated[AsyncDatabase, Depends(get_db)]  # type: ignore[type-arg]


async def current_admin(
    request: Request, db: DbDep, settings: SettingsDep
) -> dict[str, Any]:
    token = request.cookies.get(settings.auth_cookie_name)
    session, admin = await session_svc.resolve_session(db, token)
    request.state.session = session
    request.state.admin = admin
    return admin


AdminDep = Annotated[dict[str, Any], Depends(current_admin)]


async def require_business(admin: AdminDep, db: DbDep) -> dict[str, Any]:
    from app.repositories.business_repo import BusinessRepo

    business = await BusinessRepo(db).by_id(admin["business_id"])
    if business is None or not business.get("active", True):
        raise ForbiddenError("Business unavailable")
    return business


BusinessDep = Annotated[dict[str, Any], Depends(require_business)]


async def csrf_protect(
    request: Request, settings: SettingsDep
) -> None:
    """Double-submit CSRF check + Origin allowlist for cookie-auth mutations."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    origin = request.headers.get("origin")
    if origin and settings.frontend_origin_list and origin not in settings.frontend_origin_list:
        raise ForbiddenError("Origin not allowed")
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        return  # unauthenticated requests handled by auth dep
    session_hash = sha256_hex(token)
    csrf_cookie = request.cookies.get(CSRF_COOKIE)
    csrf_header = request.headers.get("x-csrf-token")
    if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
        raise ForbiddenError("CSRF validation failed")
    if not session_svc.verify_csrf(session_hash, settings.auth_csrf_secret, csrf_header):
        raise ForbiddenError("CSRF validation failed")


CsrfDep = Depends(csrf_protect)


class RateLimiter:
    """Simple in-memory fixed-window limiter (per key)."""

    def __init__(self, max_hits: int, window_seconds: int) -> None:
        self.max_hits = max_hits
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        q = self._hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.max_hits:
            raise RateLimitedError()
        q.append(now)


login_limiter = RateLimiter(max_hits=10, window_seconds=300)


def login_rate_key(request: Request, email: str) -> str:
    ip = request.client.host if request.client else "unknown"
    return f"{ip}:{email.lower().strip()}"
