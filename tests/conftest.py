"""Test configuration — testcontainers Postgres, fixtures, Docker detection."""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Prevent Windows Proactor teardown errors (the "NoneType has no attribute 'send'" bug)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ── Project root (for alembic subprocess) ───────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Docker availability ────────────────────────────────────────────────
DOCKER_AVAILABLE = True
try:
    subprocess.run(
        ["docker", "ps"],
        capture_output=True,
        timeout=5,
        check=True,
    )
except (subprocess.SubprocessError, FileNotFoundError):
    DOCKER_AVAILABLE = False


# ── Session-scoped fixtures ─────────────────────────────────────────────


@pytest.fixture(scope="session")
def pg_container():
    """Start a pgvector Postgres container via testcontainers.

    The container is started once per test session and stopped after all
    tests complete.  This gives every test a real PostgreSQL+pgvector DB
    without depending on the local Docker Compose stack being up.
    """
    if not DOCKER_AVAILABLE:
        pytest.skip("Docker unavailable")

    from testcontainers.postgres import PostgresContainer

    container = PostgresContainer(
        image="pgvector/pgvector:0.8.0-pg16",
        username="eva",
        password="eva",
        dbname="eva",
    )
    container.start()
    yield container
    container.stop()


@pytest.fixture(scope="session", autouse=True)
def setup_db(pg_container):
    """Override DATABASE_URL, run Alembic migrations, reset engine.

    This fixture runs once per session *after* the container is ready and
    *before* any test is executed.  It:

    1. Builds the test DSN from the container's mapped port.
    2. Overrides the ``DATABASE_URL`` environment variable.
    3. Clears the ``get_settings`` LRU cache so the next call reads the
       test URL.
    4. Resets engine singletons via ``reset_engine()`` so ``get_engine()``
       creates a fresh engine pointing at the test container.
    5. Runs ``alembic upgrade head`` in a subprocess to apply all
       migrations to the test DB.
    """
    host = pg_container.get_container_host_ip()
    port = pg_container.get_exposed_port(5432)
    async_url = f"postgresql+asyncpg://eva:eva@{host}:{port}/eva"

    # --- Override env var ---
    os.environ["DATABASE_URL"] = async_url

    # --- Clear settings cache so next get_settings() picks up the new URL ---
    from app.config import get_settings

    get_settings.cache_clear()

    # --- Reset engine singletons ---
    from app.db.session import reset_engine

    reset_engine()

    # --- Patch session.py to use NullPool for tests ----------------------
    # NullPool disables connection pooling so every session.close() immediately
    # releases the underlying asyncpg connection. This prevents the Windows
    # proactor event loop from trying to close pooled connections after the
    # loop is already gone (the "NoneType has no attribute 'send'" cascade).
    import sqlalchemy.pool as _sa_pool

    import app.db.session as _session_mod

    _orig_get_engine = _session_mod.get_engine

    def _test_get_engine():
        global _engine
        _engine = _session_mod._engine
        if _engine is None:
            import pgvector.asyncpg
            from sqlalchemy import event
            from sqlalchemy.ext.asyncio import create_async_engine

            _engine = create_async_engine(
                async_url,
                poolclass=_sa_pool.NullPool,
                future=True,
            )

            @event.listens_for(_engine.sync_engine, "connect")
            def _register_vector(dbapi_conn, connection_record):
                dbapi_conn.run_async(
                    lambda raw_conn: pgvector.asyncpg.register_vector(raw_conn)
                )

            _session_mod._engine = _engine
            _session_mod._session_factory = None
        return _engine

    _session_mod.get_engine = _test_get_engine

    # --- Ensure the vector extension exists before Alembic runs ----------
    # Alembic's env.py calls register_vector() before running migrations,
    # which requires the vector extension to already be present.
    import psycopg

    plain_url = async_url.replace("+asyncpg", "")
    with psycopg.connect(plain_url) as pg_conn:
        pg_conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        pg_conn.commit()

    # --- Run Alembic migrations (clean subprocess = fresh module state) ---
    env = os.environ.copy()
    # Alembic's env.py reads DATABASE_URL via get_settings()
    env["DATABASE_URL"] = async_url

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=env,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Alembic migration failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    yield

    # --- Teardown: reset engine so subsequent sessions get fresh state ---
    reset_engine()


# ── Function-scoped fixtures ────────────────────────────────────────────


@pytest.fixture
async def async_session(setup_db):
    """Provide a function-scoped async database session.

    Depends on ``setup_db`` to have overridden DATABASE_URL and applied
    migrations.
    """
    from app.db.session import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        yield session


@pytest.fixture
def reset_engine_fixture():
    """Fixture that calls ``reset_engine()`` in its teardown.

    Use this in tests that mutate engine state and want a clean slate
    for subsequent tests.
    """
    yield
    from app.db.session import reset_engine

    reset_engine()
