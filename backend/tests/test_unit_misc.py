"""Outcome derivation, state machine, CSRF, and Vapi auth tests."""

from __future__ import annotations

import hashlib
import hmac
import time

import pytest

from app.auth import sessions
from app.core.config import Settings
from app.core.errors import UnauthorizedError
from app.core.security import sha256_hex
from app.integrations.vapi.auth import verify_server_call
from app.integrations.vapi.schemas import parse_server_message
from app.schemas.common import AppointmentStatus, CallOutcome
from app.services.calls import derive_outcome


class TestOutcomeDerivation:
    def test_appointment_link_wins(self):
        assert derive_outcome({}, {"_id": "apt_1"}) == CallOutcome.APPOINTMENT_BOOKED

    def test_safety_redirect_from_script(self):
        call = {
            "transcript": "I can't assess or treat emergencies. Please call 911.",
            "tool_calls": [],
        }
        assert derive_outcome(call, None) == CallOutcome.SAFETY_REDIRECT

    def test_caller_disconnected_short_call(self):
        call = {"ended_reason": "silence-timed-out", "tool_calls": []}
        assert derive_outcome(call, None) == CallOutcome.CALLER_DISCONNECTED

    def test_booking_failed_when_book_attempted(self):
        call = {"tool_calls": ["get_available_slots", "book_appointment"], "duration_seconds": 120}
        assert derive_outcome(call, None) == CallOutcome.BOOKING_FAILED

    def test_no_slot_when_only_availability(self):
        call = {"tool_calls": ["get_available_slots"], "duration_seconds": 90}
        assert derive_outcome(call, None) == CallOutcome.NO_AVAILABLE_SLOT

    def test_info_only(self):
        call = {"tool_calls": ["get_clinic_info"], "duration_seconds": 60}
        assert derive_outcome(call, None) == CallOutcome.INFORMATION_ONLY


class TestStateMachine:
    def test_allowed_transitions(self):
        assert AppointmentStatus.can_transition("confirmed", "cancelled")
        assert AppointmentStatus.can_transition("confirmed", "completed")
        assert not AppointmentStatus.can_transition("cancelled", "confirmed")
        assert not AppointmentStatus.can_transition("completed", "cancelled")
        assert not AppointmentStatus.can_transition("cancelled", "completed")


class TestCsrf:
    def test_mint_verify(self):
        h = sha256_hex("sessiontoken")
        token = sessions.mint_csrf(h, "csrf-secret")
        assert sessions.verify_csrf(h, "csrf-secret", token)

    def test_wrong_session_or_secret(self):
        h = sha256_hex("sessiontoken")
        token = sessions.mint_csrf(h, "csrf-secret")
        assert not sessions.verify_csrf(sha256_hex("other"), "csrf-secret", token)
        assert not sessions.verify_csrf(h, "wrong", token)
        assert not sessions.verify_csrf(h, "csrf-secret", None)
        assert not sessions.verify_csrf(h, "csrf-secret", "garbage")


class TestVapiAuth:
    def _settings(self, mode="hmac") -> Settings:
        return Settings(
            mongodb_uri="mongodb://localhost:27017",
            vapi_server_credential_mode=mode,
            vapi_server_credential_secret="topsecret",
            auth_csrf_secret="x",
            offer_token_secret="y",
        )

    def test_hmac_ok(self):
        s = self._settings()
        body = b'{"message":{"type":"tool-calls"}}'
        ts = str(int(time.time()))
        sig = hmac.new(b"topsecret", f"{ts}.{body.decode()}".encode(), hashlib.sha256).hexdigest()
        verify_server_call(s, {"x-signature": sig, "x-timestamp": ts}, body)

    def test_hmac_bad_signature(self):
        s = self._settings()
        with pytest.raises(UnauthorizedError):
            verify_server_call(
                s, {"x-signature": "bad", "x-timestamp": str(int(time.time()))}, b"{}"
            )

    def test_hmac_stale_timestamp(self):
        s = self._settings()
        body = b"{}"
        ts = str(int(time.time()) - 10000)
        sig = hmac.new(b"topsecret", f"{ts}.{body.decode()}".encode(), hashlib.sha256).hexdigest()
        with pytest.raises(UnauthorizedError):
            verify_server_call(s, {"x-signature": sig, "x-timestamp": ts}, body)

    def test_bearer_mode(self):
        s = self._settings(mode="bearer")
        verify_server_call(s, {"authorization": "Bearer topsecret"}, b"{}")
        with pytest.raises(UnauthorizedError):
            verify_server_call(s, {"authorization": "Bearer nope"}, b"{}")

    def test_missing_secret_configured(self):
        s = self._settings()
        s.vapi_server_credential_secret = ""
        with pytest.raises(UnauthorizedError):
            verify_server_call(s, {}, b"{}")


class TestVapiParsing:
    def test_tool_calls_parse(self):
        body = {
            "message": {
                "type": "tool-calls",
                "call": {"id": "c1", "phoneNumberId": "pn1", "assistantId": "a1",
                         "customer": {"number": "+12145551234"}},
                "toolCallList": [{"id": "t1", "name": "get_services", "parameters": {}}],
            }
        }
        parsed = parse_server_message(body)
        assert parsed and parsed.type == "tool-calls"
        assert parsed.call.id == "c1"
        assert parsed.call.customer_number == "+12145551234"
        assert parsed.tool_calls[0].name == "get_services"

    def test_end_of_call_report_parse(self):
        body = {
            "message": {
                "type": "end-of-call-report",
                "endedReason": "hangup",
                "call": {"id": "c2"},
                "artifact": {"transcript": "AI: hi User: bye"},
                "analysis": {"summary": "Booked a cleaning"},
            }
        }
        parsed = parse_server_message(body)
        assert parsed.type == "end-of-call-report"
        assert parsed.transcript == "AI: hi User: bye"
        assert parsed.summary == "Booked a cleaning"
        assert parsed.ended_reason == "hangup"

    def test_malformed_rejected(self):
        assert parse_server_message({}) is None
        assert parse_server_message({"message": "x"}) is None
        assert parse_server_message({"message": {"call": {}}}) is None
