"""Vapi server-message parsing. Provider payloads stay in this package;
domain services never import Vapi schemas.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class VapiCallRef(BaseModel):
    """The slices of Vapi's call object we rely on."""

    model_config = {"extra": "allow"}

    id: str
    org_id: str | None = Field(default=None, alias="orgId")
    assistant_id: str | None = Field(default=None, alias="assistantId")
    phone_number_id: str | None = Field(default=None, alias="phoneNumberId")
    customer_number: str | None = None
    started_at: str | None = Field(default=None, alias="startedAt")
    ended_at: str | None = Field(default=None, alias="endedAt")

    @classmethod
    def from_payload(cls, call: dict[str, Any] | None) -> VapiCallRef | None:
        if not call or not isinstance(call, dict) or not call.get("id"):
            return None
        customer = call.get("customer") or {}
        return cls(
            id=call["id"],
            orgId=call.get("orgId"),
            assistantId=call.get("assistantId"),
            phoneNumberId=call.get("phoneNumberId"),
            customer_number=customer.get("number"),
            startedAt=call.get("startedAt"),
            endedAt=call.get("endedAt"),
        )


class VapiToolCall(BaseModel):
    model_config = {"extra": "allow"}

    id: str
    name: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class ParsedMessage(BaseModel):
    type: str
    call: VapiCallRef | None = None
    tool_calls: list[VapiToolCall] = Field(default_factory=list)
    status: str | None = None
    ended_reason: str | None = None
    transcript: str | None = None
    summary: str | None = None
    analysis: dict[str, Any] = Field(default_factory=dict)
    artifact: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)


def parse_server_message(body: dict[str, Any]) -> ParsedMessage | None:
    """Parse a Vapi server envelope. Returns None for malformed payloads."""
    message = body.get("message") if isinstance(body, dict) else None
    if not isinstance(message, dict):
        return None
    mtype = message.get("type")
    if not isinstance(mtype, str):
        return None

    call = VapiCallRef.from_payload(message.get("call"))
    artifact = message.get("artifact") or {}
    analysis = message.get("analysis") or {}

    tool_calls: list[VapiToolCall] = []
    for tc in message.get("toolCallList") or []:
        if not isinstance(tc, dict) or not tc.get("id"):
            continue
        tool_calls.append(
            VapiToolCall(
                id=tc["id"],
                name=tc.get("name") or tc.get("function", {}).get("name", ""),
                parameters=tc.get("parameters")
                or tc.get("function", {}).get("arguments")
                or {},
            )
        )

    transcript = artifact.get("transcript") if isinstance(artifact, dict) else None
    summary = None
    if isinstance(analysis, dict):
        summary = analysis.get("summary")
    if summary is None and isinstance(message.get("summary"), str):
        summary = message.get("summary")

    return ParsedMessage(
        type=mtype,
        call=call,
        tool_calls=tool_calls,
        status=message.get("status"),
        ended_reason=message.get("endedReason"),
        transcript=transcript if isinstance(transcript, str) else None,
        summary=summary if isinstance(summary, str) else None,
        analysis=analysis if isinstance(analysis, dict) else {},
        artifact=artifact if isinstance(artifact, dict) else {},
        raw=message,
    )
