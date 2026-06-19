"""Tests for app.schemas.voice — round-trip serialisation and field validation."""

import pytest
from pydantic import ValidationError

from app.schemas.voice import CallSummaryResult, VoiceEvent, VoiceEventType


# ── VoiceEventType ────────────────────────────────────────────────────────────

def test_voice_event_type_values():
    assert VoiceEventType.AUDIO_CHUNK == "audio_chunk"
    assert VoiceEventType.END_OF_AUDIO == "end_of_audio"
    assert VoiceEventType.INTERRUPT == "interrupt"
    assert VoiceEventType.SESSION_STARTED == "session_started"
    assert VoiceEventType.SESSION_ENDED == "session_ended"
    assert VoiceEventType.TRANSCRIPT == "transcript"
    assert VoiceEventType.TOOL_CALL == "tool_call"
    assert VoiceEventType.ERROR == "error"


# ── VoiceEvent round-trip ─────────────────────────────────────────────────────

def test_audio_chunk_round_trip():
    event = VoiceEvent(type=VoiceEventType.AUDIO_CHUNK, data="dGVzdA==")
    json_str = event.model_dump_json()
    restored = VoiceEvent.model_validate_json(json_str)
    assert restored.type == VoiceEventType.AUDIO_CHUNK
    assert restored.data == "dGVzdA=="


def test_session_started_round_trip():
    event = VoiceEvent(type=VoiceEventType.SESSION_STARTED, session_id="abc-123")
    restored = VoiceEvent.model_validate_json(event.model_dump_json())
    assert restored.session_id == "abc-123"
    assert restored.data is None


def test_transcript_round_trip():
    event = VoiceEvent(type=VoiceEventType.TRANSCRIPT, role="user", text="Hello!")
    restored = VoiceEvent.model_validate_json(event.model_dump_json())
    assert restored.role == "user"
    assert restored.text == "Hello!"


def test_tool_call_round_trip():
    event = VoiceEvent(
        type=VoiceEventType.TOOL_CALL, tool_name="get_billing_history", status="calling"
    )
    restored = VoiceEvent.model_validate_json(event.model_dump_json())
    assert restored.tool_name == "get_billing_history"
    assert restored.status == "calling"


def test_error_event_round_trip():
    event = VoiceEvent(type=VoiceEventType.ERROR, message="Connection lost")
    restored = VoiceEvent.model_validate_json(event.model_dump_json())
    assert restored.message == "Connection lost"


def test_optional_fields_default_to_none():
    event = VoiceEvent(type=VoiceEventType.END_OF_AUDIO)
    assert event.data is None
    assert event.text is None
    assert event.role is None
    assert event.tool_name is None
    assert event.status is None
    assert event.session_id is None
    assert event.message is None


def test_invalid_event_type_raises():
    with pytest.raises(ValidationError):
        VoiceEvent.model_validate({"type": "not_a_valid_type"})


# ── CallSummaryResult ─────────────────────────────────────────────────────────

def test_call_summary_result_round_trip():
    summary = CallSummaryResult(
        session_id="sess-001",
        conversation_summary="Customer asked about billing.",
        sources_used=["get_billing_history", "get_customer_profile"],
        reasoning_summary="Checked billing records and identified the charge.",
        recommended_next_actions=["Issue refund", "Follow up in 48h"],
    )
    restored = CallSummaryResult.model_validate_json(summary.model_dump_json())
    assert restored.session_id == "sess-001"
    assert len(restored.sources_used) == 2
    assert "Issue refund" in restored.recommended_next_actions


def test_call_summary_result_requires_fields():
    with pytest.raises(ValidationError):
        CallSummaryResult.model_validate({})
