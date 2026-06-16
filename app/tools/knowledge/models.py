"""Pydantic models for the Knowledge tool family."""

from uuid import UUID

from pydantic import BaseModel


class KnowledgeResult(BaseModel):
    """A single vector-search hit from the knowledge base."""

    id: UUID
    content: str
    metadata: dict | None = None
    similarity_score: float
