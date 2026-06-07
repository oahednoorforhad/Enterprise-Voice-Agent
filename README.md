# EVA (Enterprise Voice Assistant)

Evidence-based multi-source enterprise reasoning system with a Bangla/English
voice interface. Backend is FastAPI on Python 3.12, packaged with `uv`.

See [`EVA PRD.md`](./EVA%20PRD.md) for the full product requirements.

## Quick Start

Follow this 10-step sequence to run the backend on a fresh clone:

1. **Clone project**: Navigate to the repository root directory.
2. **Install uv**: Follow instructions at https://docs.astral.sh/uv/ to install the package manager.
3. **Synchronize environment**: Run `uv sync` to install dependencies and configure the virtual environment.
4. **Copy environment template**: Run `copy .env.example .env` (Windows) or `cp .env.example .env` (macOS/Linux).
5. **Start database**: Launch the PostgreSQL and PGVector container with `docker compose -f docker/docker-compose.yml up -d`.
6. **Verify configuration**: Confirm `DATABASE_URL` in `.env` matches your database port.
7. **Apply migrations**: Run `uv run alembic upgrade head` to build schemas and the HNSW index.
8. **Generate synthetic data**: Run `uv run python -m scripts.generate_synthetic_data --seed 42` to produce test documents.
9. **Seed tables**: Run `uv run python -m scripts.seed_db --reset` to insert mock customer records.
10. **Start server**: Run `uv run uvicorn app.main:app --reload` and verify status at http://localhost:8000/ready.

Health check: http://localhost:8000/health

## Sprint 1 Status

The foundation deliverables are complete:

- [x] **Database Schema**: 9 relational tables mapped with SQLAlchemy 2.x ORM models.
- [x] **PGVector Integration**: HNSW index created concurrently using migration transactions.
- [x] **Synthetic Dataset**: Generation script producing reproducible scenarios and guides.
- [x] **Database Seeding**: Idempotent seeding script inserting structured records.
- [x] **FastAPI Backend**: Structured logging, request middleware, and environment-driven configurations.
- [x] **Readiness Endpoints**: `/health` and `/ready` endpoints checking database connectivity.
- [x] **Integration Testing**: Pytest suite using testcontainers for isolated validation.

## Environment Variables

The following new configuration variables are defined:

- `CORS_ORIGINS`: JSON array of allowed origins for browser clients (e.g. `["http://localhost:3000"]`).
- `MOCK_AUTH_ENABLED`: Boolean flag to bypass real authentication in development (defaults to `true`).
- `EMBEDDING_DIM`: Dimensionality of vector embeddings (defaults to `768` for text-embedding-004).
- `VECTOR_INDEX_TYPE`: Index algorithm type, either `hnsw` or `ivfflat` (defaults to `hnsw`).
- `HNSW_M`: Number of connection links per node constructed in HNSW (defaults to `16`).
- `HNSW_EF_CONSTRUCTION`: Size of the dynamic candidate list for HNSW building (defaults to `64`).

## Layout

```
app/
├── api/              # FastAPI routers (HTTP + WebSocket)
├── config/           # Pydantic settings, env loading
├── db/               # Async SQLAlchemy engine, Base, session deps
├── memory/           # Session-scoped conversational memory
├── observability/    # Langfuse traces + metrics
├── orchestrator/     # Per-turn reasoning loop (intent -> tools -> reasoning)
├── reasoning/        # Cross-source reasoning engine
├── retrieval/        # PGVector search + reranking
├── schemas/          # Shared Pydantic models
├── tools/            # LLM-callable tools (the LLM never touches SQL)
│   ├── analytics/
│   ├── billing/
│   ├── customer/
│   ├── knowledge/
│   └── ticket/
├── voice/            # Gemini Native Audio streaming bridge
└── main.py           # FastAPI app factory
data/synthetic/       # Generated test fixtures
docker/               # Compose / Dockerfiles
frontend/             # Next.js + Tailwind UI
scripts/              # One-off maintenance scripts
tests/                # Pytest suite
```

## Tooling

- Python 3.12
- `uv` for dependency + virtualenv management
- FastAPI + Uvicorn
- SQLAlchemy 2.x (async) + asyncpg
- pgvector (via `pgvector` SQLAlchemy types)
- Langfuse for tracing
- pytest + ruff for tests and linting

## Sprint plan (from PRD)

1. Foundation: schema, seed data, FastAPI skeleton, PGVector setup.
2. Retrieval layer: implement the five tool families.
3. Reasoning engine: intent analysis, tool selection, evidence aggregation.
4. Voice experience: Gemini audio, memory, call summaries.
5. Evaluation & dashboard: 50 scenarios, metrics, demo UI.
