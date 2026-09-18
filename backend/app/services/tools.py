"""Voice tool implementations.

Each returns a small stable JSON dict. Failures carry code, retryable,
and a caller-safe spoken_message. Internal detail is logged only by
correlation ID — never returned.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import Settings
from app.core.errors import AppError, TemporaryFailureError
from app.core.logging import get_logger
from app.repositories.availability_repo import (
    AvailabilityExceptionRepo,
    AvailabilityRuleRepo,
)
from app.repositories.catalog_repo import ProviderRepo, ServiceRepo
from app.repositories.clinical_repo import AppointmentRepo
from app.schemas.tools import tool_failure
from app.services import booking as booking_svc
from app.services import clinic as clinic_svc
from app.services import offers as offer_svc
from app.services.availability import generate_candidates
from app.services.timeutil import fmt_local, now_utc, utc_to_local

logger = get_logger(__name__)

MAX_SPOKEN_OPTIONS = 3
MAX_RETURNED_OPTIONS = 5


async def tool_get_clinic_info(business: dict[str, Any]) -> dict[str, Any]:
    return clinic_svc.clinic_info_payload(business)


async def tool_get_services(db: AsyncDatabase, business: dict[str, Any]) -> dict[str, Any]:  # type: ignore[type-arg]
    services = await ServiceRepo(db).list_voice_bookable(business["_id"])
    providers = await ProviderRepo(db).list(business["_id"], active_only=True)
    return clinic_svc.services_payload(services, providers)


async def tool_get_available_slots(
    db: AsyncDatabase,  # type: ignore[type-arg]
    business: dict[str, Any],
    *,
    service_slug: str,
    preferred_date: str | None,
    time_window: str,
    provider_name: str | None,
    offer_secret: str,
    offer_ttl: int,
) -> dict[str, Any]:
    tzname = business["timezone"]
    service_repo = ServiceRepo(db)
    provider_repo = ProviderRepo(db)

    service = await service_repo.by_slug(business["_id"], service_slug)
    if not service or not service.get("active") or not service.get("voice_bookable"):
        return tool_failure(
            "UNSUPPORTED_SERVICE",
            "I can't book that service by phone. I can help with our standard services though.",
        )

    today_local = utc_to_local(now_utc(), tzname).date()
    if preferred_date:
        try:
            target = date.fromisoformat(preferred_date)
        except ValueError:
            return tool_failure(
                "INVALID_DETAILS", "I didn't catch that date. Could you say it again?"
            )
    else:
        target = today_local

    if target < today_local:
        return tool_failure(
            "INVALID_DETAILS", "That date is in the past. Which upcoming day works?"
        )
    horizon = today_local + timedelta(days=int(business.get("booking_horizon_days", 90)))
    if target > horizon:
        return tool_failure(
            "INVALID_DETAILS",
            "That's beyond our booking window. Could you pick a nearer date?",
        )

    # Resolve provider preference within this business.
    if provider_name:
        matches = await provider_repo.find_by_name(business["_id"], provider_name)
        if len(matches) > 1:
            names = ", ".join(p["name"] for p in matches)
            return tool_failure(
                "INVALID_DETAILS",
                f"There are a few providers with a similar name: {names}. Which one did you mean?",
            )
        if not matches:
            return tool_failure(
                "INVALID_DETAILS",
                "I couldn't find a provider by that name. "
                "I can still check the next available times for you.",
            )
        providers = matches
        if service["_id"] not in (providers[0].get("service_ids") or []):
            return tool_failure(
                "INVALID_DETAILS",
                f"{providers[0]['name']} doesn't handle that service. I can check other providers.",
            )
    else:
        providers = await _eligible_providers(db, business["_id"], service)

    if not providers:
        return tool_failure(
            "NO_AVAILABLE_SLOT",
            "No providers are configured for that service right now.",
        )

    rule_repo = AvailabilityRuleRepo(db)
    exc_repo = AvailabilityExceptionRepo(db)
    appt_repo = AppointmentRepo(db)

    rules_by_provider = {}
    exceptions_by_provider = {}
    appts_by_provider = {}
    for p in providers:
        pid = p["_id"]
        rules_by_provider[pid] = await rule_repo.list_for_provider(business["_id"], pid)
        exceptions_by_provider[pid] = await exc_repo.list_for_provider_date(
            business["_id"], pid, target.isoformat()
        )
        appts_by_provider[pid] = await appt_repo.provider_day_confirmed(
            business["_id"],
            pid,
            _day_start_utc(target, tzname),
            _day_end_utc(target, tzname),
        )

    candidates = generate_candidates(
        business=business,
        service=service,
        providers=providers,
        rules_by_provider=rules_by_provider,
        exceptions_by_provider=exceptions_by_provider,
        appointments_by_provider=appts_by_provider,
        local_date=target,
        time_window=time_window,
        limit=MAX_RETURNED_OPTIONS,
    )
    if not candidates:
        return tool_failure(
            "NO_AVAILABLE_SLOT",
            "I don't have any openings that day. Want me to try another day?",
            retryable=True,
        )

    options = []
    for c in candidates:
        token, exp = offer_svc.mint_offer(
            secret=offer_secret,
            ttl_seconds=offer_ttl,
            business_id=business["_id"],
            service_id=service["_id"],
            provider_id=c.provider_id,
            start_at=c.start_at,
            end_at=c.end_at,
            schedule_version=int(business.get("schedule_version") or 0),
        )
        options.append(
            {
                "offer_token": token,
                "local_label": fmt_local(c.start_at, tzname),
                "provider_label": c.provider_name,
                "expires_at": exp.isoformat(),
            }
        )
    return {
        "ok": True,
        "service": service["slug"],
        "date": target.isoformat(),
        "timezone": tzname,
        "options": options,
        "speak_at_most": MAX_SPOKEN_OPTIONS,
    }


async def tool_book_appointment(
    db: AsyncDatabase,  # type: ignore[type-arg]
    settings: Settings,
    business: dict[str, Any],
    *,
    call_id: str,
    vapi_call_id: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    try:
        return await booking_svc.book_appointment(
            db,
            business=business,
            call_id=call_id,
            vapi_call_id=vapi_call_id,
            patient_name=args.get("patient_name", ""),
            callback_phone=args.get("callback_phone", ""),
            offer_token=args.get("offer_token", ""),
            patient_confirmed=bool(args.get("patient_confirmed")),
            offer_secret=settings.offer_token_secret,
        )
    except TemporaryFailureError:
        raise
    except AppError as exc:
        logger.warning("book_appointment_error", code=exc.code)
        return tool_failure(exc.code, exc.message, retryable=exc.retryable)
    except Exception:
        logger.exception("book_appointment_unexpected")
        return tool_failure(
            "TEMPORARY_FAILURE",
            "I'm having trouble completing the booking right now. "
            "Please call the clinic directly to finish scheduling.",
            retryable=True,
        )


async def _eligible_providers(
    db: AsyncDatabase, business_id: str, service: dict[str, Any]  # type: ignore[type-arg]
) -> list[dict[str, Any]]:
    providers = await ProviderRepo(db).list(business_id, active_only=True)
    return [p for p in providers if service["_id"] in (p.get("service_ids") or [])]


def _day_start_utc(d: date, tzname: str):
    from app.services.timeutil import local_to_utc

    return local_to_utc(d, "00:00", tzname)


def _day_end_utc(d: date, tzname: str):
    from datetime import timedelta

    return _day_start_utc(d, tzname) + timedelta(hours=36)
