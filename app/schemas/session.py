"""Pydantic models for session management.

Defines request/response schemas for the session management API:
listing sessions, fetching session messages, and creating sessions.
"""

from __future__ import annotations

from pydantic import BaseModel


class SessionSummary(BaseModel):
    """Summary of a single conversation session for list views."""

    session_id: str
    title: str | None
    started_at: str  # ISO datetime string
    ended_at: str | None
    message_count: int
    last_message_preview: str | None


class SessionListResponse(BaseModel):
    """Response envelope for GET /api/v1/sessions."""

    sessions: list[SessionSummary]
    total: int


class MessageItem(BaseModel):
    """A single message within a session."""

    id: str
    role: str
    content: str
    created_at: str  # ISO datetime string
    tool_calls: dict | None


class SessionMessagesResponse(BaseModel):
    """Response envelope for GET /api/v1/sessions/{id}/messages."""

    session_id: str
    title: str | None
    messages: list[MessageItem]


class CreateSessionResponse(BaseModel):
    """Response returned after creating a new session."""

    session_id: str
    title: str | None
    started_at: str  # ISO datetime string
