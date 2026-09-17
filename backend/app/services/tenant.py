"""Tenant resolution for voice-provider events.

Resolution order: authenticated saved phone-number ID first, saved
assistant ID second. When both are present they must map to the same
active business. Unknown, inactive, missing, or conflicting mappings
are rejected and audited.
"""

from __future__ import annotations

from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.logging import get_logger
from app.repositories.business_repo import BusinessRepo
from app.repositories.system_repo import AuditRepo
from app.services.timeutil import now_utc

logger = get_logger(__name__)


async def resolve_business(
    db: AsyncDatabase,  # type: ignore[type-arg]
    *,
    vapi_phone_number_id: str | None,
    vapi_assistant_id: str | None,
) -> dict[str, Any]:
    repo = BusinessRepo(db)
    by_phone = (
        await repo.by_vapi_phone_number_id(vapi_phone_number_id)
        if vapi_phone_number_id
        else None
    )
    by_assistant = (
        await repo.by_vapi_assistant_id(vapi_assistant_id)
        if vapi_assistant_id
        else None
    )

    if by_phone is None and by_assistant is None:
        await _reject(db, "tenant_unmapped", vapi_phone_number_id, vapi_assistant_id)
        raise UnauthorizedError("Unrecognized voice resource mapping")

    if by_phone is not None and by_assistant is not None:
        if by_phone["_id"] != by_assistant["_id"]:
            await _reject(
                db, "tenant_conflict", vapi_phone_number_id, vapi_assistant_id,
                business_id=by_phone["_id"],
            )
            raise ForbiddenError("Conflicting tenant mapping")

    business = by_phone or by_assistant
    assert business is not None
    if not business.get("active", True):
        await _reject(
            db, "tenant_inactive", vapi_phone_number_id, vapi_assistant_id,
            business_id=business["_id"],
        )
        raise ForbiddenError("Business is inactive")
    return business


async def _reject(
    db: AsyncDatabase,  # type: ignore[type-arg]
    reason: str,
    phone_id: str | None,
    assistant_id: str | None,
    business_id: str | None = None,
) -> None:
    logger.warning(
        "tenant_resolution_rejected",
        reason=reason,
        has_phone_id=bool(phone_id),
        has_assistant_id=bool(assistant_id),
    )
    await AuditRepo(db).record(
        {
            "business_id": business_id,
            "actor": "system",
            "action": f"tenant_resolution.{reason}",
            "target_type": "vapi_resource",
            "target_id": phone_id or assistant_id or "unknown",
            "summary": {"reason": reason},
            "created_at": now_utc(),
        }
    )
