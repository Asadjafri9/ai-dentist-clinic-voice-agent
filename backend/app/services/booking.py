"""Atomic booking service.

The database — not the language model — decides whether a slot can be
booked. All validation and the single appointment insert happen inside
one MongoDB transaction guarded by the provider/day schedule document.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import (
    ConnectionFailure,
    DuplicateKeyError,
    OperationFailure,
    PyMongoError,
)

from app.core import ids
from app.core.errors import TemporaryFailureError, ValidationError
from app.core.logging import get_logger
from app.core.security import normalize_phone
from app.repositories.availability_repo import (
    AvailabilityExceptionRepo,
    AvailabilityRuleRepo,
    ScheduleDayRepo,
)
from app.repositories.catalog_repo import ProviderRepo, ServiceRepo
from app.repositories.clinical_repo import AppointmentRepo, PatientRepo
from app.repositories.system_repo import AuditRepo
from app.services import offers as offer_service
from app.services.availability import interval_fits_schedule
from app.services.timeutil import fmt_local, now_utc, utc_to_local

logger = get_logger(__name__)

MAX_TXN_ATTEMPTS = 4

BOOKED = "BOOKED"
ALREADY_BOOKED = "ALREADY_BOOKED"
SLOT_UNAVAILABLE = "SLOT_UNAVAILABLE"
OFFER_EXPIRED = "OFFER_EXPIRED"
INVALID_DETAILS = "INVALID_DETAILS"
TEMPORARY_FAILURE = "TEMPORARY_FAILURE"


async def book_appointment(
    db: AsyncDatabase,  # type: ignore[type-arg]
    *,
    business: dict[str, Any],
    call_id: str,
    vapi_call_id: str,
    patient_name: str,
    callback_phone: str,
    offer_token: str,
    patient_confirmed: bool,
    offer_secret: str,
) -> dict[str, Any]:
    """Attempt an atomic booking. Returns a stable result envelope."""

    if not patient_confirmed:
        return _result(
            INVALID_DETAILS,
            "I need your explicit confirmation before booking.",
            field="patient_confirmed",
        )

    offer = offer_service.verify_offer(offer_token, offer_secret)
    if offer is None or offer.business_id != business["_id"]:
        return _result(
            INVALID_DETAILS,
            "That appointment option isn't valid. Let me check times again.",
            field="offer_token",
        )
    if offer.expires_at <= now_utc():
        return _result(
            OFFER_EXPIRED,
            "That time option just expired. Let me pull fresh availability.",
        )

    try:
        phone = normalize_phone(callback_phone)
    except ValidationError:
        return _result(
            INVALID_DETAILS,
            "That phone number doesn't look right. Could you repeat it?",
            field="callback_phone",
        )
    name = patient_name.strip()
    if not name:
        return _result(INVALID_DETAILS, "I still need the patient's name.", field="patient_name")

    service_repo = ServiceRepo(db)
    provider_repo = ProviderRepo(db)
    service = await service_repo.by_id(business["_id"], offer.service_id)
    provider = await provider_repo.by_id(business["_id"], offer.provider_id)
    if not service or not service.get("active") or not service.get("voice_bookable"):
        return _result(
            INVALID_DETAILS, "That service is no longer bookable by phone.", field="service"
        )
    if not provider or not provider.get("active"):
        return _result(
            INVALID_DETAILS, "That provider is no longer available.", field="provider"
        )
    if offer.service_id not in (provider.get("service_ids") or []):
        return _result(
            INVALID_DETAILS,
            "That provider doesn't offer that service.",
            field="provider",
        )

    intent = offer_service.booking_intent_for(business["_id"], call_id, offer.offer_id)

    last_error: Exception | None = None
    for attempt in range(MAX_TXN_ATTEMPTS):
        try:
            return await _book_in_transaction(
                db,
                business=business,
                service=service,
                provider=provider,
                offer=offer,
                call_id=call_id,
                vapi_call_id=vapi_call_id,
                patient_name=name,
                phone=phone,
                booking_intent_id=intent,
            )
        except DuplicateKeyError:
            existing = await AppointmentRepo(db).by_booking_intent(business["_id"], intent)
            if existing:
                return _booked_result(existing, business, already=True)
            return _result(TEMPORARY_FAILURE, "I couldn't confirm the booking.", retryable=True)
        except (OperationFailure, ConnectionFailure) as exc:
            if _is_retryable_txn(exc) and attempt < MAX_TXN_ATTEMPTS - 1:
                last_error = exc
                await asyncio.sleep(0.05 * (attempt + 1))
                continue
            logger.warning("booking_txn_failed", error=str(exc), attempt=attempt)
            last_error = exc
            break
        except PyMongoError as exc:
            logger.warning("booking_db_error", error=str(exc))
            last_error = exc
            break

    if last_error is not None:
        raise TemporaryFailureError("Booking could not be completed") from last_error
    return _result(TEMPORARY_FAILURE, "I couldn't confirm the booking.", retryable=True)


async def _book_in_transaction(
    db: AsyncDatabase,  # type: ignore[type-arg]
    *,
    business: dict[str, Any],
    service: dict[str, Any],
    provider: dict[str, Any],
    offer: offer_service.OfferPayload,
    call_id: str,
    vapi_call_id: str,
    patient_name: str,
    phone: str,
    booking_intent_id: str,
) -> dict[str, Any]:
    client = db.client
    appt_repo = AppointmentRepo(db)
    patient_repo = PatientRepo(db)
    rule_repo = AvailabilityRuleRepo(db)
    exc_repo = AvailabilityExceptionRepo(db)
    day_repo = ScheduleDayRepo(db)
    audit_repo = AuditRepo(db)

    async with client.start_session() as session:
        async with await session.start_transaction():
            # 1. Idempotent replay: same booking intent -> original result.
            existing = await appt_repo.by_booking_intent(
                business["_id"], booking_intent_id, session=session
            )
            if existing:
                return _booked_result(existing, business, already=True)

            # 2. Lock the provider/day schedule document.
            local_date = utc_to_local(offer.start_at, business["timezone"]).date()
            await day_repo.lock(
                business["_id"], offer.provider_id, local_date, session=session
            )

            # 3. Overlap check inside the transaction.
            overlaps = await appt_repo.overlapping(
                business["_id"],
                offer.provider_id,
                offer.start_at,
                offer.end_at,
                session=session,
            )
            if overlaps:
                return _result(
                    SLOT_UNAVAILABLE,
                    "That time was just taken. Let me check other options.",
                )

            # 4. Revalidate schedule, buffers, horizon.
            rules = await rule_repo.list_for_provider(business["_id"], offer.provider_id)
            exceptions = await exc_repo.list_for_provider_date(
                business["_id"], offer.provider_id, local_date.isoformat()
            )
            day_appts = await appt_repo.provider_day_confirmed(
                business["_id"],
                offer.provider_id,
                offer.start_at - timedelta(hours=24),
                offer.end_at + timedelta(hours=24),
                session=session,
            )
            if not interval_fits_schedule(
                business=business,
                service=service,
                provider_id=offer.provider_id,
                rules=rules,
                exceptions=exceptions,
                appointments=day_appts,
                start_at=offer.start_at,
                end_at=offer.end_at,
            ):
                return _result(
                    SLOT_UNAVAILABLE,
                    "That time no longer fits the schedule. Let me check again.",
                )

            # 5. Upsert patient, insert appointment, audit.
            patient = await patient_repo.upsert_by_phone(
                business["_id"], phone, patient_name, ids.patient_id(), session=session
            )
            appt_doc = {
                "_id": ids.appointment_id(),
                "business_id": business["_id"],
                "patient_id": patient["_id"],
                "provider_id": provider["_id"],
                "service_id": service["_id"],
                "call_id": call_id,
                "vapi_call_id": vapi_call_id,
                "booking_intent_id": booking_intent_id,
                "patient_name": patient_name,
                "patient_phone": phone,
                "start_at": offer.start_at,
                "end_at": offer.end_at,
                "timezone": business["timezone"],
                "status": "confirmed",
                "source": "voice",
                "created_at": now_utc(),
                "updated_at": now_utc(),
            }
            await appt_repo.insert(appt_doc, session=session)
            await audit_repo.record(
                {
                    "business_id": business["_id"],
                    "actor": "voice_agent",
                    "action": "appointment.booked",
                    "target_type": "appointment",
                    "target_id": appt_doc["_id"],
                    "summary": {
                        "service": service.get("slug"),
                        "provider": provider.get("name"),
                        "start_at": offer.start_at.isoformat(),
                    },
                    "created_at": now_utc(),
                },
                session=session,
            )
            return _booked_result(appt_doc, business, provider=provider)


def _booked_result(
    appt: dict[str, Any], business: dict[str, Any], *, already: bool = False,
    provider: dict[str, Any] | None = None,
) -> dict[str, Any]:
    local = fmt_local(appt["start_at"], business["timezone"])
    provider_label = (provider or {}).get("name") or appt.get("provider_name") or ""
    return {
        "ok": True,
        "code": ALREADY_BOOKED if already else BOOKED,
        "appointment_id": appt["_id"],
        "local_label": local,
        "provider_label": provider_label,
        "spoken_message": (
            f"You're confirmed for {local}"
            + (f" with {provider_label}" if provider_label else "")
            + "."
        ),
    }


def _result(
    code: str, spoken_message: str, *, field: str | None = None, retryable: bool = False
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "ok": code in (BOOKED, ALREADY_BOOKED),
        "code": code,
        "retryable": retryable,
        "spoken_message": spoken_message,
    }
    if field:
        out["field"] = field
    return out


def _is_retryable_txn(exc: Exception) -> bool:
    has_label = getattr(exc, "has_error_label", None)
    if callable(has_label):
        return bool(
            has_label("TransientTransactionError")
            or has_label("UnknownTransactionCommitResult")
        )
    labels = getattr(exc, "error_labels", None) or []
    return any(
        lbl in labels
        for lbl in ("TransientTransactionError", "UnknownTransactionCommitResult")
    )
