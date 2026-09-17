"""FastAPI application entrypoint."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    auth,
    availability,
    business,
    catalog,
    health,
    integrations_vapi,
    operations,
)
from app.core.config import get_settings
from app.core.errors import AppError, error_envelope
from app.core.logging import configure_logging, get_logger
from app.db.client import close_client, init_client
from app.db.indexes import ensure_indexes

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    client = init_client(settings.mongodb_uri)
    app.state.db = client[settings.mongodb_database]
    await ensure_indexes(app.state.db)
    logger.info("app_started", env=settings.app_env)
    yield
    await close_client()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AI Dentist Voice Agent API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    cors_kwargs: dict = {
        "allow_origins": settings.frontend_origin_list,
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "X-CSRF-Token"],
    }
    if not settings.is_production:
        # Dev: allow any localhost/127.0.0.1 port (e.g. preview proxies).
        cors_kwargs["allow_origin_regex"] = r"https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?"
    app.add_middleware(CORSMiddleware, **cors_kwargs)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex[:16]}"
        request.state.request_id = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("unhandled_error")
            return JSONResponse(
                {
                    "success": False,
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "An internal error occurred.",
                        "retryable": False,
                        "request_id": request_id,
                    },
                },
                status_code=500,
            )
        response.headers["x-request-id"] = request_id
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        rid = getattr(request.state, "request_id", "req_unknown")
        return JSONResponse(error_envelope(exc, rid), status_code=exc.http_status)

    @app.exception_handler(401)
    async def unauthorized_handler(request: Request, exc) -> JSONResponse:
        rid = getattr(request.state, "request_id", "req_unknown")
        return JSONResponse(
            {
                "success": False,
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Authentication required.",
                    "retryable": False,
                    "request_id": rid,
                }
            },
            status_code=401,
        )

    v1 = APIRouter(prefix="/api/v1")
    for r in (
        health.router,
        auth.router,
        business.router,
        catalog.services_router,
        catalog.providers_router,
        availability.router,
        operations.patients_router,
        operations.appointments_router,
        operations.calls_router,
        operations.dashboard_router,
        integrations_vapi.router,
    ):
        v1.include_router(r)

    app.include_router(v1)

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
