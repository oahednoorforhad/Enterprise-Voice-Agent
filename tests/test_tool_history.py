"""Tests for the History tool — get_session_history and format helpers."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest

from app.db.models import ConversationSession, Customer
from app.tools.history.functions import format_summaries_for_prompt, get_session_history
from app.tools.history.models import SessionHistoryResult

pytestmark = pytest.mark.asyncio

CUSTOMER_ID = uuid.uuid4()

_SUMMARY_JSON = json.dumps({
    "conversation_summary": "Customer asked about duplicate charge in March.",
    "sources_used": ["billing_records", "policies"],
    "reasoning_summary": "Confirmed duplicate via billing history.",
    "recommended_next_actions": ["Apply credit to April invoice"],
})


def _make_session(
    customer_id: uuid.UUID,
    status: str = "completed",
    summary: str | None = _SUMMARY_JSON,
    days_ago: int = 1,
) -> ConversationSession:
    started = datetime(2026, 6, 19 - days_ago, 10, 0, 0, tzinfo=UTC)
    return ConversationSession(
        id=uuid.uuid4(),
        customer_id=customer_id,
        session_status=status,
        started_at=started,
        ended_at=started,
        language="en",
        summary=summary,
    )


# ── Setup helper ──────────────────────────────────────────────────────────────

async def _seed_customer(session, customer_id: uuid.UUID) -> None:
    session.add(Customer(
        id=customer_id,
        name="Test User",
        email=f"{customer_id}@test.com",
        is_active=True,
    ))
    await session.flush()


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestGetSessionHistory:

    async def test_returns_empty_when_no_sessions(self, async_session):
        cid = uuid.uuid4()
        await _seed_customer(async_session, cid)
        await async_session.commit()

        result = await get_session_history(async_session, cid)

        assert isinstance(result, SessionHistoryResult)
        assert result.sessions == []
        assert result.total == 0

    async def test_returns_completed_sessions_with_summary(self, async_session):
        cid = uuid.uuid4()
        await _seed_customer(async_session, cid)
        async_session.add(_make_session(cid, status="completed", days_ago=1))
        async_session.add(_make_session(cid, status="closed",    days_ago=2))
        await async_session.commit()

        result = await get_session_history(async_session, cid)

        assert result.total == 2
        assert all(s.conversation_summary for s in result.sessions)

    async def test_skips_sessions_with_null_summary(self, async_session):
        cid = uuid.uuid4()
        await _seed_customer(async_session, cid)
        async_session.add(_make_session(cid, summary=None,        days_ago=1))
        async_session.add(_make_session(cid, summary=_SUMMARY_JSON, days_ago=2))
        await async_session.commit()

        result = await get_session_history(async_session, cid)

        assert result.total == 1

    async def test_skips_active_sessions(self, async_session):
        cid = uuid.uuid4()
        await _seed_customer(async_session, cid)
        async_session.add(_make_session(cid, status="active",    days_ago=0))
        async_session.add(_make_session(cid, status="completed", days_ago=1))
        await async_session.commit()

        result = await get_session_history(async_session, cid)

        assert result.total == 1
        assert result.sessions[0].conversation_summary == "Customer asked about duplicate charge in March."

    async def test_returns_most_recent_first(self, async_session):
        cid = uuid.uuid4()
        await _seed_customer(async_session, cid)

        old_summary = json.dumps({"conversation_summary": "Old session.", "sources_used": [], "recommended_next_actions": []})
        new_summary = json.dumps({"conversation_summary": "New session.", "sources_used": [], "recommended_next_actions": []})

        async_session.add(_make_session(cid, summary=old_summary, days_ago=5))
        async_session.add(_make_session(cid, summary=new_summary, days_ago=1))
        await async_session.commit()

        result = await get_session_history(async_session, cid)

        assert result.sessions[0].conversation_summary == "New session."
        assert result.sessions[1].conversation_summary == "Old session."

    async def test_respects_limit(self, async_session):
        cid = uuid.uuid4()
        await _seed_customer(async_session, cid)
        for i in range(5):
            async_session.add(_make_session(cid, days_ago=i + 1))
        await async_session.commit()

        result = await get_session_history(async_session, cid, limit=3)

        assert result.total == 3

    async def test_parses_json_summary_fields(self, async_session):
        cid = uuid.uuid4()
        await _seed_customer(async_session, cid)
        async_session.add(_make_session(cid))
        await async_session.commit()

        result = await get_session_history(async_session, cid)

        item = result.sessions[0]
        assert item.conversation_summary == "Customer asked about duplicate charge in March."
        assert "billing_records" in item.sources_used
        assert "Apply credit to April invoice" in item.recommended_next_actions

    async def test_handles_plain_text_summary(self, async_session):
        cid = uuid.uuid4()
        await _seed_customer(async_session, cid)
        async_session.add(_make_session(cid, summary="Plain text summary."))
        await async_session.commit()

        result = await get_session_history(async_session, cid)

        assert result.sessions[0].conversation_summary == "Plain text summary."
        assert result.sessions[0].sources_used == []


class TestFormatSummariesForPrompt:

    async def test_empty_result_returns_no_prior_message(self, async_session):
        cid = uuid.uuid4()
        await _seed_customer(async_session, cid)
        await async_session.commit()

        result = await get_session_history(async_session, cid)
        formatted = format_summaries_for_prompt(result)

        assert formatted == "No prior sessions on record."

    async def test_formats_sessions_as_bullet_points(self, async_session):
        cid = uuid.uuid4()
        await _seed_customer(async_session, cid)
        async_session.add(_make_session(cid, days_ago=1))
        await async_session.commit()

        result = await get_session_history(async_session, cid)
        formatted = format_summaries_for_prompt(result)

        assert formatted.startswith("-")
        assert "Customer asked about duplicate charge" in formatted
