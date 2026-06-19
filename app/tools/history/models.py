"""Pydantic response models for the History tool."""

from __future__ import annotations

from pydantic import BaseModel


class SessionHistoryItem(BaseModel):
    """Summary of one completed conversation session."""

    session_id: str
    date: str                           # ISO date string of session start
    conversation_summary: str           # plain-text summary of what was discussed
    sources_used: list[str] = []        # tools / data sources referenced
    recommended_next_actions: list[str] = []  # follow-up suggestions


class SessionHistoryResult(BaseModel):
    """Aggregated result returned by get_session_history."""

    sessions: list[SessionHistoryItem]
    total: int                          # number of sessions returned
