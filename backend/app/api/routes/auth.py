"""Admin authentication: login, logout, me."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.api.deps import AdminDep, CsrfDep, DbDep, SettingsDep, login_limiter, login_rate_key
from app.auth import passwords, sessions
from app.auth.sessions import CSRF_COOKIE
from app.core.errors import UnauthorizedError
from app.core.security import sha256_hex
from app.repositories.system_repo import AdminUserRepo, SessionRepo
from app.schemas.admin import LoginRequest
from app.schemas.common import ok

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookies(
    response: Response, settings, session_token: str, csrf_token: str
) -> None:
    secure = settings.auth_cookie_secure and settings.is_production
    samesite = settings.auth_cookie_samesite
    if samesite == "none" and not secure:
        samesite = "lax"  # browsers reject SameSite=None without Secure
    common = {
        "secure": secure,
        "httponly": True,
        "samesite": samesite,
        "path": "/",
        "max_age": settings.auth_session_ttl_hours * 3600,
    }
    response.set_cookie(settings.auth_cookie_name, session_token, **common)
    # CSRF cookie is readable by JS (double-submit pattern).
    response.set_cookie(
        CSRF_COOKIE, csrf_token, **{**common, "httponly": False}
    )


@router.post("/login")
async def login(
    payload: LoginRequest, request: Request, response: Response, db: DbDep, settings: SettingsDep
) -> dict:
    email = payload.email.lower().strip()
    login_limiter.check(login_rate_key(request, email))

    admin = await AdminUserRepo(db).by_email(email)
    # Generic failure — never reveal whether the account exists.
    if admin is None or not admin.get("active", True):
        raise UnauthorizedError("Invalid email or password")
    if not passwords.verify_password(admin["password_hash"], payload.password):
        raise UnauthorizedError("Invalid email or password")

    session_token, session = await sessions.create_session(
        db, admin["_id"], settings.auth_session_ttl_hours
    )
    csrf = sessions.mint_csrf(sha256_hex(session_token), settings.auth_csrf_secret)
    _set_auth_cookies(response, settings, session_token, csrf)
    await AdminUserRepo(db).touch_login(admin["_id"])
    return ok(
        {
            "admin": {
                "id": admin["_id"],
                "email": admin["email"],
                "role": admin.get("role", "owner"),
                "business_id": admin["business_id"],
            }
        }
    )


@router.post("/logout", dependencies=[CsrfDep])
async def logout(request: Request, response: Response, db: DbDep, settings: SettingsDep) -> dict:
    token = request.cookies.get(settings.auth_cookie_name)
    if token:
        session = await SessionRepo(db).by_token_hash(sha256_hex(token))
        if session:
            await SessionRepo(db).revoke(session["_id"])
    response.delete_cookie(settings.auth_cookie_name, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return ok({"logged_out": True})


@router.get("/me")
async def me(admin: AdminDep, db: DbDep) -> dict:
    from app.repositories.business_repo import BusinessRepo

    business = await BusinessRepo(db).by_id(admin["business_id"])
    return ok(
        {
            "admin": {
                "id": admin["_id"],
                "email": admin["email"],
                "role": admin.get("role", "owner"),
            },
            "business": {
                "id": business["_id"] if business else None,
                "name": business.get("name") if business else None,
                "timezone": business.get("timezone") if business else None,
            },
        }
    )
