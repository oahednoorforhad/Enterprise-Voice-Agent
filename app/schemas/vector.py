"""Pydantic models for vector / embedding operations."""

from pydantic import BaseModel


class VectorItem(BaseModel):
    """A single document + embedding to be upserted into the vector store."""

    id: str
    collection: str
    title: str
    content: str
    source_ref: str = ""
    metadata: dict = {}
    embedding: list[float]


class SearchResult(BaseModel):
    """A search hit with similarity score."""

    id: str
    collection: str
    title: str
    content: str
    source_ref: str
    metadata: dict
    score: float
