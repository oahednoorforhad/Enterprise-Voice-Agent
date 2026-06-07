"""Application configuration loaded from environment variables.

Centralised settings keep credentials and tunables out of code so the
LLM, database, and observability layers can be configured per-env.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the EVA backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # General
    app_name: str = "EVA Backend"
    environment: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:3000"]
    mock_auth_enabled: bool = True

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://eva:eva@localhost:5432/eva",
        description="Async SQLAlchemy DSN for the primary PostgreSQL database.",
    )
    db_pool_size: int = 10
    db_max_overflow: int = 5

    # Vector store (PGVector)
    vector_collection_documentation: str = "documentation"
    vector_collection_policies: str = "policies"
    vector_collection_articles: str = "knowledge_articles"
    vector_collection_troubleshooting: str = "troubleshooting_guides"
    embedding_model: str = "text-embedding-004"
    embedding_dim: int = 768
    vector_index_type: Literal["hnsw", "ivfflat"] = "hnsw"
    hnsw_m: int = 16
    hnsw_ef_construction: int = 64

    # LLM / Voice
    google_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_audio_model: str = "gemini-2.0-flash"

    # Observability
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # Reasoning
    max_tool_calls_per_turn: int = 6
    retrieval_top_k: int = 5


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()
