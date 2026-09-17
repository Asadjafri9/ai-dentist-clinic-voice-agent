"""Security primitives: HMAC signing, constant-time compare, phone normalization."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any

import phonenumbers

from app.core.errors import ValidationError

DEFAULT_PHONE_REGION = "US"


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hmac_sha256(secret: str, payload: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(raw: str) -> bytes:
    pad = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + pad)


def sign_payload(payload: dict[str, Any], secret: str) -> str:
    """Compact signed token: base64url(json).base64url(hmac)."""
    body = _b64e(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    sig = _b64e(
        hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    )
    return f"{body}.{sig}"


def verify_payload(token: str, secret: str) -> dict[str, Any] | None:
    """Return decoded payload if signature is valid, else None."""
    try:
        body, sig = token.split(".", 1)
    except ValueError:
        return None
    expected = _b64e(
        hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    )
    if not hmac.compare_digest(expected, sig):
        return None
    try:
        decoded = json.loads(_b64d(body))
    except (ValueError, json.JSONDecodeError):
        return None
    return decoded if isinstance(decoded, dict) else None


def normalize_phone(raw: str, region: str = DEFAULT_PHONE_REGION) -> str:
    """Normalize to E.164. Raises ValidationError for invalid numbers."""
    if not raw or not raw.strip():
        raise ValidationError("A callback phone number is required.")
    try:
        parsed = phonenumbers.parse(raw.strip(), region)
    except phonenumbers.NumberParseException as exc:
        raise ValidationError("That phone number does not look valid.") from exc
    if not phonenumbers.is_valid_number(parsed):
        raise ValidationError("That phone number does not look valid.")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def try_normalize_phone(raw: str | None, region: str = DEFAULT_PHONE_REGION) -> str | None:
    if not raw:
        return None
    try:
        return normalize_phone(raw, region)
    except ValidationError:
        return None


def phone_suffix(e164: str | None) -> str | None:
    if not e164:
        return None
    digits = "".join(c for c in e164 if c.isdigit())
    return digits[-4:] if len(digits) >= 4 else None
