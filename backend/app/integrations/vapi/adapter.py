"""Vapi server endpoint dispatch.

One endpoint handles supported message types. Synchronous tool calls
return one result per provider toolCallId; informational events are
persisted to the durable inbox + jobs queue and acknowledged quickly.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import timedelta
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from app.core import ids
from app.core.config import Settings
from app.core.errors import ValidationError
from app.core.logging import get_logger
from app.integrations.vapi.schemas import ParsedMessage
from app.repositories.clinical_repo import CallRepo
from app.repositories.system_repo import IntegrationEventRepo, ToolResultRepo
from app.schemas.tools import tool_failure
from app.services import jobs as job_svc
from app.services import tools as tool_svc
from app.services.timeutil import now_utc

logger = get_logger(__name__)

INFORMATIONAL_TYPES = {
    "status-update",
    "end-of-call-report",
    "transcript",
    "conversation-update",
    "speech-update",
    "assistant.speechStarted",
    "hang",
    "model-output",
    "user-interrupted",
    "voice-input",
}

SUPPORTED_SYNC_TYPES = {"tool-calls"}

TOOL_NAMES = {
    "get_clinic_info",
    "get_services",
    "get_available_slots",
    "book_appointment",
}


def event_fingerprint(business_id: str, parsed: ParsedMessage, raw_body: bytes) -> str:
    """Stable dedupe fingerprint across provider retries."""
    call_key = parsed.call.id if parsed.call else "nocall"
    provider_event = parsed.raw.get("id") or parsed.raw.get("eventId") or ""
    payload_hash = hashlib.sha256(raw_body).hexdigest()[:32]
    base = f"vapi|{business_id}|{call_key}|{parsed.type}|{provider_event}|{payload_hash}"
    return hashlib.sha256(base.encode()).hexdigest()


async def handle_message(
    db: AsyncDatabase,  # type: ignore[type-arg]
    settings: Settings,
    business: dict[str, Any],
    parsed: ParsedMessage,
    raw_body: bytes,
) -> dict[str, Any] | None:
    """Process one authenticated, tenant-resolved message.

    Returns a response body for synchronous types, else None.
    """
    fingerprint = event_fingerprint(business["_id"], parsed, raw_body)
    event_repo = IntegrationEventRepo(db)

    inserted = await event_repo.insert_inbox(
        {
            "_id": ids.event_id(),
            "provider": "vapi",
            "business_id": business["_id"],
            "call_id": parsed.call.id if parsed.call else None,
            "message_type": parsed.type,
            "fingerprint": fingerprint,
            "status": "received",
            "attempts": 0,
            "created_at": now_utc(),
            "updated_at": now_utc(),
            "expires_at": now_utc() + timedelta(days=30),
        }
    )
    if not inserted:
        prior = await event_repo.by_fingerprint(fingerprint)
        logger.info("duplicate_event", fingerprint=fingerprint)
        if parsed.type == "tool-calls" and prior and prior.get("response"):
            return prior["response"]
        return None

    if parsed.type in SUPPORTED_SYNC_TYPES:
        try:
            response = await asyncio.wait_for(
                _handle_tool_calls(db, settings, business, parsed),
                timeout=settings.vapi_tool_timeout_seconds + 1.5,
            )
        except TimeoutError:
            logger.warning("tool_calls_timeout")
            response = {
                "results": [
                    {
                        "toolCallId": tc.id,
                        "name": tc.name,
                        "result": json.dumps(
                            tool_failure(
                                "TEMPORARY_FAILURE",
                                "I'm having a little trouble reaching our system. One moment.",
                                retryable=True,
                            )
                        ),
                    }
                    for tc in parsed.tool_calls
                ]
            }
        await event_repo.set_status(fingerprint, "processed", response=response)
        return response

    if parsed.type in INFORMATIONAL_TYPES or parsed.type == "assistant-request":
        await job_svc.enqueue(
            db,
            job_svc.JOB_PROCESS_CALL_EVENT,
            {"message": parsed.raw, "raw": raw_body.decode("utf-8", "replace")},
            business_id=business["_id"],
        )
        await event_repo.set_status(fingerprint, "queued")
        return None

    # Unsupported but harmless message type — acknowledge without processing.
    await event_repo.set_status(fingerprint, "ignored")
    return None


async def _handle_tool_calls(
    db: AsyncDatabase,  # type: ignore[type-arg]
    settings: Settings,
    business: dict[str, Any],
    parsed: ParsedMessage,
) -> dict[str, Any]:
    if not parsed.call:
        return {
            "results": [
                {
                    "toolCallId": tc.id,
                    "name": tc.name,
                    "result": json.dumps(
                        tool_failure("TEMPORARY_FAILURE", "I couldn't verify this call.", True)
                    ),
                }
                for tc in parsed.tool_calls
            ]
        }

    call_repo = CallRepo(db)
    call_doc = await call_repo.upsert_in_progress(
        business["_id"],
        parsed.call.id,
        {
            "status": "in-progress",
            "caller_phone": parsed.call.customer_number,
            "started_at": parsed.call.started_at,
        },
    )
    internal_call_id = call_doc["_id"]

    results = []
    for tc in parsed.tool_calls:
        result = await _execute_tool_idempotent(
            db, settings, business, call_repo, internal_call_id, parsed.call.id, tc
        )
        results.append(
            {"toolCallId": tc.id, "name": tc.name, "result": json.dumps(result)}
        )
    return {"results": results}


async def _execute_tool_idempotent(
    db: AsyncDatabase,  # type: ignore[type-arg]
    settings: Settings,
    business: dict[str, Any],
    call_repo: CallRepo,
    internal_call_id: str,
    vapi_call_id: str,
    tc,
) -> dict[str, Any]:
    tool_repo = ToolResultRepo(db)
    prior = await tool_repo.get(business["_id"], internal_call_id, tc.id)
    if prior is not None:
        return prior["result"]

    if tc.name not in TOOL_NAMES:
        result = tool_failure(
            "UNSUPPORTED_TOOL", "I can't do that, but I can help book an appointment."
        )
    else:
        try:
            result = await asyncio.wait_for(
                _dispatch_tool(
                    db, settings, business, internal_call_id, vapi_call_id, tc
                ),
                timeout=settings.vapi_tool_timeout_seconds,
            )
        except TimeoutError:
            result = tool_failure(
                "TEMPORARY_FAILURE",
                "That took too long. Let me try that again.",
                retryable=True,
            )
        except Exception:
            logger.exception("tool_execution_failed", tool=tc.name)
            result = tool_failure(
                "TEMPORARY_FAILURE",
                "I'm having trouble with our system right now.",
                retryable=True,
            )

    await tool_repo.insert(
        {
            "business_id": business["_id"],
            "call_id": internal_call_id,
            "vapi_call_id": vapi_call_id,
            "tool_call_id": tc.id,
            "tool_name": tc.name,
            "result": result,
            "created_at": now_utc(),
        }
    )
    await call_repo.record_tool_call(business["_id"], internal_call_id, tc.name)
    return result


async def _dispatch_tool(
    db: AsyncDatabase,  # type: ignore[type-arg]
    settings: Settings,
    business: dict[str, Any],
    internal_call_id: str,
    vapi_call_id: str,
    tc,
) -> dict[str, Any]:
    args = tc.parameters or {}
    if tc.name == "get_clinic_info":
        return await tool_svc.tool_get_clinic_info(business)
    if tc.name == "get_services":
        return await tool_svc.tool_get_services(db, business)
    if tc.name == "get_available_slots":
        return await tool_svc.tool_get_available_slots(
            db,
            business,
            service_slug=str(args.get("service_slug", "")),
            preferred_date=args.get("preferred_date"),
            time_window=args.get("time_window") or "any",
            provider_name=args.get("provider_name"),
            offer_secret=settings.offer_token_secret,
            offer_ttl=settings.offer_token_ttl_seconds,
        )
    if tc.name == "book_appointment":
        return await tool_svc.tool_book_appointment(
            db,
            settings,
            business,
            call_id=internal_call_id,
            vapi_call_id=vapi_call_id,
            args=args,
        )
    raise ValidationError(f"unknown tool {tc.name}")
