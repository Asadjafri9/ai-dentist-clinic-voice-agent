"""Durable job handlers.

- process_call_event: applies informational Vapi events to call records
- retention_purge: deletes expired transcript content
- voice_config_sync: pushes assistant configuration to Vapi
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import Settings
from app.core.logging import get_logger
from app.integrations.vapi.assistant import (
    VapiClient,
    build_assistant_config,
    config_version,
)
from app.integrations.vapi.schemas import parse_server_message
from app.repositories.business_repo import BusinessRepo
from app.repositories.clinical_repo import CallRepo
from app.services.calls import derive_outcome, link_appointment_for_call
from app.services.timeutil import now_utc

logger = get_logger(__name__)


async def handle_process_call_event(
    db: AsyncDatabase, job: dict[str, Any], settings: Settings  # type: ignore[type-arg]
) -> None:
    message = job["payload"].get("message") or {}
    parsed = parse_server_message({"message": message})
    business_id = job.get("business_id")
    if parsed is None or business_id is None:
        return

    call_repo = CallRepo(db)
    vapi_call_id = parsed.call.id if parsed.call else message.get("call", {}).get("id")
    if not vapi_call_id:
        return

    if parsed.type == "status-update":
        fields: dict[str, Any] = {"status": parsed.status}
        if parsed.call and parsed.call.customer_number:
            fields["caller_phone"] = parsed.call.customer_number
        if parsed.status == "in-progress" and parsed.call and parsed.call.started_at:
            fields["started_at"] = parsed.call.started_at
        if parsed.status == "ended" and parsed.call and parsed.call.ended_at:
            fields["ended_at"] = parsed.call.ended_at
        await call_repo.upsert_in_progress(business_id, vapi_call_id, fields)
        return

    if parsed.type == "end-of-call-report":
        call = await call_repo.upsert_in_progress(
            business_id, vapi_call_id, {"status": "ended"}
        )
        update: dict[str, Any] = {
            "ended_reason": parsed.ended_reason,
            "ended_at": (parsed.call.ended_at if parsed.call else None),
        }
        if parsed.call and parsed.call.started_at and parsed.call.ended_at:
            try:
                from datetime import datetime

                start = datetime.fromisoformat(parsed.call.started_at.replace("Z", "+00:00"))
                end = datetime.fromisoformat(parsed.call.ended_at.replace("Z", "+00:00"))
                update["duration_seconds"] = max(0, int((end - start).total_seconds()))
            except ValueError:
                pass
        if parsed.transcript:
            update["transcript"] = parsed.transcript
            update["transcript_status"] = "stored"
            update["transcript_expires_at"] = now_utc() + timedelta(
                days=settings.transcript_retention_days
            )
        if parsed.summary:
            update["summary"] = parsed.summary
            update["summary_status"] = "stored"
        else:
            update["summary_status"] = "processing"
        structured = (parsed.analysis or {}).get("structuredData") or {}
        update["analysis"] = {
            "intent": structured.get("intent"),
            "caller_name": structured.get("caller_name"),
            "requested_service": structured.get("requested_service"),
            "requested_provider": structured.get("requested_provider"),
            "emergency_statement": structured.get("emergency_statement"),
        }
        business = await BusinessRepo(db).by_id(business_id)
        update["prompt_version"] = (business or {}).get("voice_sync", {}).get(
            "assistant_version"
        )
        update["vapi_assistant_id"] = (parsed.call.assistant_id if parsed.call else None)
        await call_repo.update(business_id, call["_id"], update)

        # Authoritative links + derived outcome.
        appt = await link_appointment_for_call(db, business_id, call["_id"])
        links: dict[str, Any] = {}
        if appt:
            links["appointment_id"] = appt["_id"]
            links["patient_id"] = appt.get("patient_id")
        refreshed = await call_repo.by_id(business_id, call["_id"])
        outcome = derive_outcome({**(refreshed or {}), **update}, appt)
        await call_repo.update(
            business_id, call["_id"], {**links, "outcome": outcome}
        )
        logger.info("call_finalized", outcome=outcome)
        return

    # transcript / conversation-update / hang etc.: ensure a record exists.
    if parsed.type in {"transcript", "conversation-update", "hang", "speech-update"}:
        if parsed.type == "hang":
            logger.info("vapi_hang", call=vapi_call_id[-6:])
        return


async def handle_retention_purge(
    db: AsyncDatabase, job: dict[str, Any], settings: Settings  # type: ignore[type-arg]
) -> None:
    """Delete expired transcript content and record deletion status."""
    now = now_utc()
    expired = (
        await db["calls"]
        .find(
            {
                "transcript_expires_at": {"$lte": now},
                "transcript_status": "stored",
            }
        )
        .limit(500)
        .to_list(None)
    )
    for call in expired:
        await db["calls"].update_one(
            {"_id": call["_id"]},
            {
                "$unset": {"transcript": "", "analysis": ""},
                "$set": {
                    "transcript_status": "deleted",
                    "transcript_deleted_at": now,
                    "updated_at": now,
                },
            },
        )
    if expired:
        logger.info("transcripts_purged", count=len(expired))


async def handle_voice_sync(
    db: AsyncDatabase, job: dict[str, Any], settings: Settings  # type: ignore[type-arg]
) -> None:
    business_id = job["payload"]["business_id"]
    repo = BusinessRepo(db)
    business = await repo.by_id(business_id)
    if business is None:
        return
    assistant_id = business.get("vapi_assistant_id")
    if not assistant_id or not settings.vapi_api_key:
        await repo.set_voice_sync(business_id, "unconfigured", error="missing vapi ids")
        return
    server_url = f"{settings.api_base_url}/api/v1/integrations/vapi/server"
    credential_id = (business.get("voice") or {}).get("credential_id")
    config = build_assistant_config(
        business, server_url=server_url, credential_id=credential_id
    )
    version = config_version(config)
    try:
        client = VapiClient(settings)
        await client.update_assistant(assistant_id, config)
    except Exception as exc:
        await repo.set_voice_sync(business_id, "error", error=str(exc)[:200])
        raise
    await repo.set_voice_sync(
        business_id, "synced", synced_at=now_utc(), error=None, assistant_version=version
    )


HANDLERS = {
    "process_call_event": handle_process_call_event,
    "retention_purge": handle_retention_purge,
    "voice_config_sync": handle_voice_sync,
}
