"""Post-session call summary generation (FR-10).

Uses the existing text ``LLMClient.generate_structured()`` — *not* Gemini
Live — so no audio infrastructure is required and the call is fully
synchronous with normal retry/observability semantics.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from app.core.llm_client import LLMClient
from app.schemas.voice import CallSummaryResult

logger = logging.getLogger(__name__)

_SYSTEM_INSTRUCTION = """\
You are an enterprise CRM analytics assistant. Summarise a completed
customer support voice call concisely and accurately. Extract the key
discussion points, the data sources consulted, and the recommended
follow-up actions.  Respond ONLY with the requested JSON — no prose.
"""


class _SummaryInput(BaseModel):
    """Internal schema describing the prompt payload (not the response)."""

    session_id: str
    transcript_lines: list[str]
    tools_called: list[str]
    customer_context: dict


async def generate_call_summary(
    llm_client: LLMClient,
    session_id: str,
    transcript: list[dict],
    tools_called: list[str],
    customer_context: dict | None = None,
) -> CallSummaryResult:
    """Generate a structured call summary using the LLM.

    Parameters
    ----------
    llm_client:
        The injected ``LLMClient`` instance (uses text generation, not audio).
    session_id:
        UUID string identifying the voice session — returned verbatim in the
        ``CallSummaryResult`` so the caller can correlate the result.
    transcript:
        List of ``{"role": "user"|"assistant", "text": "..."}`` dicts
        accumulated during the session.
    tools_called:
        Ordered list of tool names called during the session, e.g.
        ``["get_customer_profile", "get_billing_history"]``.
    customer_context:
        Optional dict with customer metadata (name, email, plan_tier, …)
        injected into the prompt for richer summaries.

    Returns
    -------
    CallSummaryResult
        Four-field structured summary ready for persistence.
    """
    ctx = customer_context or {}

    # Build readable transcript
    transcript_text = "\n".join(
        f"{turn['role'].upper()}: {turn['text']}"
        for turn in transcript
        if turn.get("text")
    ) or "(no transcript available)"

    tools_text = (
        ", ".join(dict.fromkeys(tools_called))  # deduplicated, order-preserved
        if tools_called
        else "none"
    )

    customer_info = (
        f"Customer: {ctx.get('name', 'Unknown')} "
        f"(plan: {ctx.get('plan_tier', 'unknown')}, "
        f"email: {ctx.get('email', 'unknown')})"
    )

    prompt = f"""\
Generate a structured call summary for the following voice session.

{customer_info}
Session ID: {session_id}
Tools consulted: {tools_text}

--- Transcript ---
{transcript_text}
--- End transcript ---

Respond with a JSON object matching exactly this schema:
{{
  "session_id": "<session_id string>",
  "conversation_summary": "<2-4 sentence plain-text summary of the call>",
  "sources_used": ["<tool_name_1>", "<tool_name_2>", ...],
  "reasoning_summary": "<1-2 sentences about how the agent arrived at its answers>",
  "recommended_next_actions": ["<action 1>", "<action 2>", ...]
}}
"""

    try:
        result = await llm_client.generate_structured(
            prompt=prompt,
            response_schema=CallSummaryResult,
            system_instruction=_SYSTEM_INSTRUCTION,
        )
        # Ensure session_id matches (model may hallucinate a different value)
        if result.session_id != session_id:
            result = result.model_copy(update={"session_id": session_id})
        return result
    except Exception as exc:  # noqa: BLE001
        logger.warning("generate_call_summary failed: %s — returning fallback", exc)
        return CallSummaryResult(
            session_id=session_id,
            conversation_summary="Summary generation failed. Please review the transcript manually.",
            sources_used=list(dict.fromkeys(tools_called)),
            reasoning_summary="LLM summary generation encountered an error.",
            recommended_next_actions=["Review call transcript manually"],
        )
