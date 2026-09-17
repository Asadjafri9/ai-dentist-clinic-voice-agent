"""POST /integrations/vapi/server — the single Vapi entry point.

Order: size check -> authenticate -> parse -> resolve tenant -> inbox ->
dispatch. Synchronous tool calls return results; everything else is
queued durably and acknowledged.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.deps import DbDep, SettingsDep
from app.core.logging import get_logger
from app.integrations.vapi import adapter
from app.integrations.vapi.auth import verify_server_call
from app.integrations.vapi.schemas import parse_server_message
from app.services.tenant import resolve_business

logger = get_logger(__name__)

router = APIRouter(prefix="/integrations/vapi", tags=["vapi"])

MAX_BODY_BYTES = 1_000_000


@router.post("/server")
async def vapi_server(request: Request, db: DbDep, settings: SettingsDep) -> JSONResponse:
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        return JSONResponse({"error": "payload too large"}, status_code=413)

    verify_server_call(settings, request.headers, raw)

    try:
        body = json_loads(raw)
    except ValueError:
        return JSONResponse({"error": "invalid json"}, status_code=400)

    parsed = parse_server_message(body)
    if parsed is None:
        return JSONResponse({"error": "unsupported message"}, status_code=400)

    phone_number_id = None
    assistant_id = None
    if parsed.call:
        phone_number_id = parsed.call.phone_number_id
        assistant_id = parsed.call.assistant_id
    phone_number_id = phone_number_id or _nested(body, "phoneNumber", "id")
    assistant_id = assistant_id or _nested(body, "message", "assistantId") or _nested(
        body, "message", "assistant", "id"
    )

    business = await resolve_business(
        db, vapi_phone_number_id=phone_number_id, vapi_assistant_id=assistant_id
    )

    response = await adapter.handle_message(db, settings, business, parsed, raw)
    return JSONResponse(response or {"ok": True})


def _nested(obj, *path):
    cur = obj
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def json_loads(raw: bytes):
    import json

    return json.loads(raw)
