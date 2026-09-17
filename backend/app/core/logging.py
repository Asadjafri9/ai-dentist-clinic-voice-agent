"""Structured logging with automatic sensitive-field redaction.

No full transcripts, phone numbers, auth tokens, or provider payloads
may appear in routine logs.
"""

from __future__ import annotations

import logging
import re
from collections.abc import MutableMapping
from typing import Any

import structlog

SENSITIVE_KEYS = frozenset(
    {
        "password",
        "token",
        "secret",
        "authorization",
        "cookie",
        "session_token",
        "api_key",
        "apikey",
        "transcript",
        "messages",
        "recording_url",
        "offer_token",
        "phone",
        "phone_number",
        "callback_phone",
        "patient_phone",
    }
)

_PHONE_RE = re.compile(r"\+?\d[\d\s\-()]{7,}\d")


def _redact_value(key: str, value: Any) -> Any:
    lowered = key.lower()
    if lowered in SENSITIVE_KEYS or any(k in lowered for k in SENSITIVE_KEYS):
        if isinstance(value, str) and len(value) >= 4:
            return f"***{value[-4:]}"
        return "***"
    if isinstance(value, str) and _PHONE_RE.search(value):
        return _PHONE_RE.sub(lambda m: f"***{m.group(0)[-4:]}", value)
    if isinstance(value, dict):
        return {k: _redact_value(k, v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(key, v) for v in value]
    return value


def redact_processor(
    logger: logging.Logger, method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    for key in list(event_dict.keys()):
        if key in ("event", "timestamp", "level"):
            continue
        event_dict[key] = _redact_value(key, event_dict[key])
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            redact_processor,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
