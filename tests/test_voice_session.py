"""Tests for app.voice.session — GeminiLiveSession and helpers."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.voice.session import GeminiLiveSession, _build_system_prompt


# ── _build_system_prompt ──────────────────────────────────────────────────────

def test_build_system_prompt_includes_customer_info():
    ctx = {
        "name": "Acme Corp",
        "email": "billing@acme.com",
        "company": "Acme Inc",
        "plan_tier": "enterprise",
    }
    prompt = _build_system_prompt(ctx)
    assert "Acme Corp" in prompt
    assert "billing@acme.com" in prompt
    assert "enterprise" in prompt


def test_build_system_prompt_defaults_on_missing_context():
    prompt = _build_system_prompt({})
    assert "Valued Customer" in prompt
    # Should not raise
    assert isinstance(prompt, str) and len(prompt) > 0


# ── GeminiLiveSession init ────────────────────────────────────────────────────

def test_session_id_is_uuid():
    sess = GeminiLiveSession(customer_id=str(uuid.uuid4()))
    # Should be valid UUID
    uuid.UUID(sess.session_id)


def test_initial_transcript_empty():
    sess = GeminiLiveSession(customer_id=str(uuid.uuid4()))
    assert sess.transcript == []
    assert sess.tools_called == []


def test_customer_id_string_coerced_to_uuid():
    uid = uuid.uuid4()
    sess = GeminiLiveSession(customer_id=str(uid))
    assert sess._customer_id == uid


def test_customer_id_uuid_accepted():
    uid = uuid.uuid4()
    sess = GeminiLiveSession(customer_id=uid)
    assert sess._customer_id == uid


# ── GeminiLiveSession._handle_response ───────────────────────────────────────

def _make_session(customer_id=None):
    return GeminiLiveSession(
        customer_id=customer_id or str(uuid.uuid4()),
        session_factory=MagicMock(),
    )


@pytest.mark.asyncio
async def test_handle_response_audio_chunk_sent_to_browser():
    sess = _make_session()
    ws = AsyncMock()

    # Build a mock response with audio data
    inline = MagicMock()
    inline.data = b"\x00\x01" * 100

    part = MagicMock()
    part.inline_data = inline

    model_turn = MagicMock()
    model_turn.parts = [part]

    server_content = MagicMock()
    server_content.model_turn = model_turn
    server_content.input_transcription = None
    server_content.output_transcription = None

    response = MagicMock()
    response.server_content = server_content
    response.tool_call = None

    live_session = AsyncMock()
    await sess._handle_response(ws, live_session, response)

    ws.send_text.assert_called_once()
    payload = ws.send_text.call_args[0][0]
    assert '"audio_chunk"' in payload
    assert '"data"' in payload


@pytest.mark.asyncio
async def test_handle_response_input_transcript_appended():
    sess = _make_session()
    ws = AsyncMock()

    in_trans = MagicMock()
    in_trans.text = "Hello EVA"

    server_content = MagicMock()
    server_content.model_turn = None
    server_content.input_transcription = in_trans
    server_content.output_transcription = None

    response = MagicMock()
    response.server_content = server_content
    response.tool_call = None

    await sess._handle_response(ws, AsyncMock(), response)

    assert len(sess._transcript) == 1
    assert sess._transcript[0] == {"role": "user", "text": "Hello EVA"}


@pytest.mark.asyncio
async def test_handle_response_output_transcript_appended():
    sess = _make_session()
    ws = AsyncMock()

    out_trans = MagicMock()
    out_trans.text = "How can I help you?"

    server_content = MagicMock()
    server_content.model_turn = None
    server_content.input_transcription = None
    server_content.output_transcription = out_trans

    response = MagicMock()
    response.server_content = server_content
    response.tool_call = None

    await sess._handle_response(ws, AsyncMock(), response)

    assert sess._transcript[0]["role"] == "assistant"
    assert sess._transcript[0]["text"] == "How can I help you?"


@pytest.mark.asyncio
async def test_handle_response_tool_call_dispatched():
    sess = _make_session()
    ws = AsyncMock()
    live_session = AsyncMock()

    fc = MagicMock()
    fc.name = "get_billing_history"
    fc.id = "fc-001"
    fc.args = {}

    tool_call = MagicMock()
    tool_call.function_calls = [fc]

    response = MagicMock()
    response.server_content = None
    response.tool_call = tool_call

    with patch(
        "app.voice.session.dispatch_tool",
        new=AsyncMock(return_value={"records": []}),
    ):
        await sess._handle_response(ws, live_session, response)

    assert "get_billing_history" in sess._tools_called
    # Two send_text calls: "calling" and "done"
    calls = [c[0][0] for c in ws.send_text.call_args_list]
    assert any('"calling"' in c for c in calls)
    assert any('"done"' in c for c in calls)
    # Tool response was sent to Gemini
    live_session.send.assert_called_once()


@pytest.mark.asyncio
async def test_handle_response_no_server_content_no_error():
    """Response with no server_content and no tool_call must not raise."""
    sess = _make_session()
    ws = AsyncMock()

    response = MagicMock()
    response.server_content = None
    response.tool_call = None

    await sess._handle_response(ws, AsyncMock(), response)
    ws.send_text.assert_not_called()
