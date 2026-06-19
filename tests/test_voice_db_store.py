"""Tests for DbConversationStore.update_session_summary()."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.memory.db_store import DbConversationStore


def _make_session_mock(existing_conv_session=None):
    """Return an AsyncSession mock with a controllable execute result."""
    mock_scalar = MagicMock()
    mock_scalar.scalar_one_or_none = MagicMock(return_value=existing_conv_session)

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_scalar)
    mock_db.flush = AsyncMock()
    return mock_db


def _make_conv_session(customer_id):
    sess = MagicMock()
    sess.id = uuid.uuid4()
    sess.customer_id = customer_id
    sess.voice_session_id = None
    sess.summary = None
    sess.tools_used = None
    sess.audio_duration_seconds = None
    sess.session_status = "active"
    sess.ended_at = None
    return sess


@pytest.mark.asyncio
async def test_update_session_summary_returns_true_when_found():
    customer_uid = uuid.uuid4()
    conv = _make_conv_session(customer_uid)
    db = _make_session_mock(existing_conv_session=conv)

    store = DbConversationStore()
    result = await store.update_session_summary(
        session=db,
        customer_id=str(customer_uid),
        summary='{"session_id": "vs-001"}',
        tools_used=["get_billing_history"],
        voice_session_id="vs-001",
        audio_duration_seconds=120,
    )

    assert result is True
    assert conv.summary == '{"session_id": "vs-001"}'
    assert conv.session_status == "closed"
    assert conv.tools_used == {"tools": ["get_billing_history"]}
    assert conv.voice_session_id == "vs-001"
    assert conv.audio_duration_seconds == 120
    db.flush.assert_called_once()


@pytest.mark.asyncio
async def test_update_session_summary_returns_false_when_not_found():
    customer_uid = uuid.uuid4()
    db = _make_session_mock(existing_conv_session=None)

    store = DbConversationStore()
    result = await store.update_session_summary(
        session=db,
        customer_id=str(customer_uid),
        summary='{"session_id": "vs-missing"}',
    )

    assert result is False


@pytest.mark.asyncio
async def test_update_session_summary_no_voice_session_id():
    """Without voice_session_id, it falls back to the active session."""
    customer_uid = uuid.uuid4()
    conv = _make_conv_session(customer_uid)
    db = _make_session_mock(existing_conv_session=conv)

    store = DbConversationStore()
    result = await store.update_session_summary(
        session=db,
        customer_id=str(customer_uid),
        summary="plain summary",
        tools_used=None,
    )

    assert result is True
    assert conv.summary == "plain summary"
    # tools_used should remain unchanged when None is passed
    assert conv.tools_used is None


@pytest.mark.asyncio
async def test_update_session_summary_sets_ended_at():
    customer_uid = uuid.uuid4()
    conv = _make_conv_session(customer_uid)
    db = _make_session_mock(existing_conv_session=conv)

    store = DbConversationStore()
    await store.update_session_summary(
        session=db,
        customer_id=str(customer_uid),
        summary="test",
    )

    # ended_at should be set to func.now() (a SQLAlchemy expression, not None)
    assert conv.ended_at is not None
