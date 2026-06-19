"""Tests for app.voice.summary — generate_call_summary()."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.voice import CallSummaryResult
from app.voice.summary import generate_call_summary


def _make_llm_client(return_value: CallSummaryResult | None = None, raise_exc=None):
    client = MagicMock()
    if raise_exc:
        client.generate_structured = AsyncMock(side_effect=raise_exc)
    else:
        client.generate_structured = AsyncMock(return_value=return_value)
    return client


@pytest.mark.asyncio
async def test_generate_call_summary_basic():
    expected = CallSummaryResult(
        session_id="sess-001",
        conversation_summary="Customer asked about billing.",
        sources_used=["get_billing_history"],
        reasoning_summary="Retrieved and reviewed billing records.",
        recommended_next_actions=["Issue refund"],
    )
    client = _make_llm_client(return_value=expected)

    result = await generate_call_summary(
        llm_client=client,
        session_id="sess-001",
        transcript=[
            {"role": "user", "text": "Why was I charged twice?"},
            {"role": "assistant", "text": "Let me check your billing history."},
        ],
        tools_called=["get_billing_history"],
        customer_context={"name": "Acme", "plan_tier": "enterprise"},
    )

    assert result.session_id == "sess-001"
    assert result.conversation_summary == "Customer asked about billing."
    client.generate_structured.assert_called_once()


@pytest.mark.asyncio
async def test_generate_call_summary_corrects_session_id():
    """If the model returns a wrong session_id, it must be overwritten."""
    wrong_id_result = CallSummaryResult(
        session_id="wrong-id",
        conversation_summary="Summary text.",
        sources_used=[],
        reasoning_summary="Reasoning.",
        recommended_next_actions=[],
    )
    client = _make_llm_client(return_value=wrong_id_result)

    result = await generate_call_summary(
        llm_client=client,
        session_id="correct-id",
        transcript=[{"role": "user", "text": "Hello"}],
        tools_called=[],
    )

    assert result.session_id == "correct-id"


@pytest.mark.asyncio
async def test_generate_call_summary_fallback_on_error():
    """On LLM failure, returns a sensible fallback (does not raise)."""
    client = _make_llm_client(raise_exc=RuntimeError("LLM unavailable"))

    result = await generate_call_summary(
        llm_client=client,
        session_id="sess-fail",
        transcript=[{"role": "user", "text": "Test"}],
        tools_called=["get_customer_profile"],
    )

    assert isinstance(result, CallSummaryResult)
    assert result.session_id == "sess-fail"
    assert "failed" in result.conversation_summary.lower() or "error" in result.conversation_summary.lower()
    # sources_used should include tools_called in fallback
    assert "get_customer_profile" in result.sources_used


@pytest.mark.asyncio
async def test_generate_call_summary_empty_transcript():
    expected = CallSummaryResult(
        session_id="sess-empty",
        conversation_summary="No conversation recorded.",
        sources_used=[],
        reasoning_summary="No data to analyse.",
        recommended_next_actions=[],
    )
    client = _make_llm_client(return_value=expected)

    result = await generate_call_summary(
        llm_client=client,
        session_id="sess-empty",
        transcript=[],
        tools_called=[],
    )

    assert result.session_id == "sess-empty"
    # Verify the "(no transcript available)" placeholder was used in the prompt
    call_prompt = client.generate_structured.call_args.kwargs.get(
        "prompt"
    ) or client.generate_structured.call_args.args[0]
    assert "no transcript" in call_prompt.lower()


@pytest.mark.asyncio
async def test_generate_call_summary_tools_deduped_in_prompt():
    """Repeated tool names should appear only once in the prompt."""
    expected = CallSummaryResult(
        session_id="sess-dedup",
        conversation_summary="x",
        sources_used=[],
        reasoning_summary="y",
        recommended_next_actions=[],
    )
    client = _make_llm_client(return_value=expected)

    await generate_call_summary(
        llm_client=client,
        session_id="sess-dedup",
        transcript=[{"role": "user", "text": "Hi"}],
        tools_called=["get_billing_history", "get_billing_history", "search_policies"],
    )

    call_prompt = client.generate_structured.call_args.kwargs.get(
        "prompt"
    ) or client.generate_structured.call_args.args[0]
    # Count occurrences — should appear only once
    assert call_prompt.count("get_billing_history") == 1
