"""Structured application errors and the API error envelope.

Raw exceptions must never leak to clients or tool responses.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base application error carrying a stable machine code."""

    code = "INTERNAL_ERROR"
    http_status = 500
    retryable = False
    public_message = "An internal error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        http_status: int | None = None,
        retryable: bool | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message or self.public_message)
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status
        if retryable is not None:
            self.retryable = retryable
        self.details = details or {}

    @property
    def message(self) -> str:
        return str(self)


class NotFoundError(AppError):
    code = "NOT_FOUND"
    http_status = 404
    public_message = "The requested resource was not found."


class UnauthorizedError(AppError):
    code = "UNAUTHORIZED"
    http_status = 401
    public_message = "Authentication required."


class ForbiddenError(AppError):
    code = "FORBIDDEN"
    http_status = 403
    public_message = "You do not have access to this resource."


class ValidationError(AppError):
    code = "INVALID_DETAILS"
    http_status = 422
    public_message = "The request contains invalid details."


class ConflictError(AppError):
    code = "CONFLICT"
    http_status = 409
    public_message = "The request conflicts with current state."


class RateLimitedError(AppError):
    code = "RATE_LIMITED"
    http_status = 429
    retryable = True
    public_message = "Too many requests. Please try again later."


class TemporaryFailureError(AppError):
    code = "TEMPORARY_FAILURE"
    http_status = 503
    retryable = True
    public_message = "The service is temporarily unavailable."


class SlotUnavailableError(AppError):
    code = "SLOT_UNAVAILABLE"
    http_status = 409
    retryable = True
    public_message = "That appointment time is no longer available."


class OfferExpiredError(AppError):
    code = "OFFER_EXPIRED"
    http_status = 409
    retryable = True
    public_message = "That appointment option expired. Please pick a new time."


def error_envelope(exc: AppError, request_id: str) -> dict[str, Any]:
    return {
        "success": False,
        "error": {
            "code": exc.code,
            "message": exc.message,
            "retryable": exc.retryable,
            "request_id": request_id,
        },
    }
