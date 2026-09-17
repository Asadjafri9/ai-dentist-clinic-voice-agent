"""Vapi server-call authentication.

Supports a saved custom credential in either mode:
- bearer: constant-time compare of a configured header value
- hmac: hex(HMAC_SHA256(secret, f"{timestamp}.{body}")) in the signature
  header plus a timestamp header validated against a replay skew window.

Header names are configuration, not hard-coded assumptions.
"""

from __future__ import annotations

import hmac
import time
from collections.abc import Mapping
from hashlib import sha256

from app.core.config import Settings
from app.core.errors import UnauthorizedError
from app.core.logging import get_logger

logger = get_logger(__name__)


def verify_server_call(
    settings: Settings,
    headers: Mapping[str, str],
    raw_body: bytes,
) -> None:
    """Raise UnauthorizedError when the event cannot be authenticated."""
    secret = settings.vapi_server_credential_secret
    if not secret:
        logger.warning("vapi_auth_not_configured")
        raise UnauthorizedError("Voice integration not configured")

    lowered = {k.lower(): v for k, v in headers.items()}

    if settings.vapi_server_credential_mode == "bearer":
        presented = lowered.get(settings.vapi_bearer_header.lower(), "")
        expected_values = {secret, f"Bearer {secret}"}
        if not any(hmac.compare_digest(presented, e) for e in expected_values):
            raise UnauthorizedError("Invalid voice credential")
        return

    # HMAC mode
    signature = lowered.get(settings.vapi_server_credential_header.lower(), "")
    timestamp = lowered.get(settings.vapi_server_timestamp_header.lower(), "")
    if not signature or not timestamp:
        raise UnauthorizedError("Missing voice signature")

    try:
        ts = int(timestamp)
    except ValueError:
        # allow epoch millis
        try:
            ts = int(float(timestamp)) // 1000
        except ValueError:
            raise UnauthorizedError("Malformed voice timestamp") from None
    if ts > 10_000_000_000:  # millis
        ts = ts // 1000
    if abs(time.time() - ts) > settings.vapi_max_replay_skew_seconds:
        raise UnauthorizedError("Stale voice signature")

    expected = hmac.new(
        secret.encode(), f"{timestamp}.{raw_body.decode('utf-8', 'replace')}".encode(), sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature.lower()):
        raise UnauthorizedError("Invalid voice signature")
