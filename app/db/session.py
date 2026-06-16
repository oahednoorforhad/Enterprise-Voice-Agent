"""Async SQLAlchemy engine and session factory.

The LLM never issues raw SQL — it only calls tools in `app/tools/`.
The engine here is used exclusively by the tool implementations.
"""

from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Lazily build the async engine so tests can override settings first."""

    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_pre_ping=True,
            future=True,
        )

        @event.listens_for(_engine.sync_engine, "connect")
        def _register_vector(dbapi_conn, connection_record):
            """Register pgvector type codecs on the raw asyncpg connection.

            ``pgvector.asyncpg.register_vector`` is a coroutine, but the
            ``sync_engine.connect`` event fires synchronously. The raw
            ``dbapi_conn`` is an ``AsyncAdapt_asyncpg_connection`` which
            wraps the real asyncpg connection and exposes ``run_async``
            to bridge sync→async without nested event loops.
            """
            import pgvector.asyncpg

            dbapi_conn.run_async(
                lambda raw_conn: pgvector.asyncpg.register_vector(raw_conn)
            )

    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the session factory, initialising the engine if needed."""

    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields an async session per request."""

    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise e


async def dispose_engine() -> None:
    """Tear the engine down (used on application shutdown)."""

    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


def reset_engine() -> None:
    """Reset engine singletons — call in test teardown to allow re-init with new settings."""

    global _engine, _session_factory
    _engine = None
    _session_factory = None
