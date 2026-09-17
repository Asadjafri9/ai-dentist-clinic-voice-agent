"""Short-lived signed offer tokens.

A token binds business, service, provider, exact interval, schedule
revision, and expiry. The model can select an offer but cannot
manufacture trusted slot or provider data. A token is not a
reservation and does not guarantee availability.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.security import sign_payload, verify_payload
from app.services.timeutil import now_utc


@dataclass(frozen=True)
class OfferPayload:
    offer_id: str
    business_id: str
    service_id: str
    provider_id: str
    start_at: datetime
    end_at: datetime
    schedule_version: int
    expires_at: datetime


def mint_offer(
    *,
    secret: str,
    ttl_seconds: int,
    business_id: str,
    service_id: str,
    provider_id: str,
    start_at: datetime,
    end_at: datetime,
    schedule_version: int,
) -> tuple[str, datetime]:
    exp = now_utc() + timedelta(seconds=ttl_seconds)
    payload = {
        "oid": secrets.token_hex(8),
        "biz": business_id,
        "svc": service_id,
        "prv": provider_id,
        "st": start_at.isoformat(),
        "en": end_at.isoformat(),
        "rev": schedule_version,
        "exp": exp.isoformat(),
    }
    return sign_payload(payload, secret), exp


def verify_offer(token: str, secret: str) -> OfferPayload | None:
    """Return the payload when signature is valid; does NOT check expiry
    (caller decides expiry semantics). Returns None on tamper."""
    data = verify_payload(token, secret)
    if data is None:
        return None
    try:
        return OfferPayload(
            offer_id=data["oid"],
            business_id=data["biz"],
            service_id=data["svc"],
            provider_id=data["prv"],
            start_at=datetime.fromisoformat(data["st"]),
            end_at=datetime.fromisoformat(data["en"]),
            schedule_version=int(data["rev"]),
            expires_at=datetime.fromisoformat(data["exp"]),
        )
    except (KeyError, ValueError, TypeError):
        return None


def booking_intent_for(business_id: str, call_id: str, offer_id: str) -> str:
    """Deterministic booking intent from trusted fields.

    A call cannot silently create a second intent for the same offer;
    a different offer (different slot) yields a different intent.
    """
    import hashlib

    digest = hashlib.sha256(f"{business_id}:{call_id}:{offer_id}".encode()).hexdigest()[:24]
    return f"bi_{digest}"
