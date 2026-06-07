# EVA Sprint 1 — Foundation

## TL;DR

> **Quick Summary**: Stand up the complete EVA backend foundation: Postgres 16 + pgvector via Docker, 9 ORM-mapped tables, two Alembic migrations, a VectorStore wrapper, idempotent Faker-driven seed data, a FastAPI surface with `/health` + `/ready`, structured logging, settings-driven CORS, a request-log middleware, a minimal mock-auth stub, and a ≥10-test pytest suite — all without touching Sprint 2–5 modules.
>
> **Deliverables**:
> - `docker/docker-compose.yml` — single Postgres 16 + pgvector service
> - `app/db/models.py` — 9 ORM models (8 relational + 1 vector)
> - `migrations/` — Alembic async setup + 2 migrations (tables → HNSW indexes)
> - `app/retrieval/vector_store.py` — VectorStore with cosine search
> - `app/api/deps.py` — mock-auth stub `get_current_user()`
> - `scripts/seed_db.py` — idempotent seed (20+ customers, 24+ docs structure)
> - `data/synthetic/eval_scenarios.jsonl` — 50 evaluation scenarios (Faker seed=42)
> - `data/synthetic/docs/` — 12 markdown files × 4 collections = 48 docs
> - Updated: `app/config/settings.py`, `app/db/session.py`, `app/main.py`, `pyproject.toml`, `.env.example`, `README.md`
>
> **Estimated Effort**: Medium (2–3 days)
> **Parallel Execution**: YES — 3 waves
> **Critical Path**: Task 1 → Task 4 → Task 5 → Task 6 → Task 7 → Task 10 → F1–F4

---

## Context

### Original Request
The user provided a 12-task Sprint 1 plan and asked: "rewrite the plan and re-evaluate according to the EVA PRD Sprint 1 — do what's best for this MVP, I need plan only for SPRINT 1."

### Codebase State (verified by file reads)
The scaffold already exists:
- `app/main.py` — FastAPI factory, `/health`, `allow_origins=["*"]` (hardcoded, overwritten in Task 8)
- `app/config/settings.py` — Pydantic Settings (database_url, google_api_key, embedding_model, etc.)
- `app/db/session.py` — Async SQLAlchemy engine, `Base`, `get_db_session()`, singleton pattern
- `app/db/__init__.py` — re-exports Base + session helpers
- `tests/test_health.py` — 1 smoke test
- `docker/`, `scripts/`, `data/synthetic/` — empty directories
- All Sprint 2–5 packages exist as empty `__init__.py` stubs

### What The Plan Does NOT Touch
`app/tools/`, `app/orchestrator/`, `app/reasoning/`, `app/voice/`, `app/memory/`, `app/evaluation/` — Sprint 2–5 territory.

### Metis Review
**Gaps identified and resolved**:
- Use `pgvector/pgvector:0.8.0-pg16` image (not plain `postgres:16`) — testcontainers AND docker-compose
- Two Alembic migrations: (1) extension + tables, (2) HNSW indexes — avoids extension race condition
- `register_vector` must be on BOTH async engine and Alembic sync engine
- Add `reset_engine()` to `session.py` for test teardown isolation
- Factory-boy removed — Faker + simple functions is sufficient for MVP seed
- T7 (generator) + T8 (seed CLI) merged into one task (tight coupling)
- Mock-auth stub is a sub-task of the FastAPI surface task, ≤15 LOC, no middleware
- `/ready` DOES ping the DB (PRD DoD-3 requirement) — kept as-is
- `python-slugify` removed (no use case in Sprint 1)
- No embedding generation during seed (no Gemini API calls)

---

## Work Objectives

### Core Objective
Deliver a runnable, fully-tested EVA backend foundation with a real Postgres+pgvector backend, versioned Alembic schema, Faker-seeded CloudDesk CRM dataset, and a FastAPI surface ready for Sprint 2 tooling.

### Concrete Deliverables
- Docker Compose stack with Postgres 16 + pgvector extension active
- 9 ORM models tracked by Alembic migrations (round-trip tested)
- VectorStore wrapper exposing cosine search over 4 collections
- 50-scenario evaluation JSONL + 48 CloudDesk markdown docs
- Idempotent seed CLI (INSERT ON CONFLICT DO NOTHING)
- `/health` (liveness) and `/ready` (DB + vector extension ping)
- structlog JSON/pretty, CORS from settings, request-log middleware
- Mock-auth stub in `app/api/deps.py`
- pytest suite: ≥10 tests, ≥70% coverage, testcontainers fallback

### Definition of Done
- [ ] `docker compose -f docker/docker-compose.yml up -d` exits 0 and `SELECT extname FROM pg_extension WHERE extname='vector'` returns 1 row
- [ ] `uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head` — all exit 0
- [ ] `uv run python -m scripts.seed_db` twice — second run inserts 0 new rows
- [ ] `curl http://localhost:8000/health` → `{"status":"ok"}`
- [ ] `curl http://localhost:8000/ready` → `{"status":"ready","db":true,"vector":true}` (200)
- [ ] `uv run pytest -q` → ≥10 passed, 0 failures, ≥70% coverage

### Must Have
- `pgvector/pgvector:0.8.0-pg16` Docker image used consistently (compose + testcontainers)
- Two Alembic migrations in correct order (tables before indexes)
- `register_vector` hook on BOTH async and Alembic sync engines
- `reset_engine()` function in `session.py` for test teardown
- `.env.example` updated in lockstep with every new Settings field
- Seed idempotency via unique constraints + `INSERT ON CONFLICT DO NOTHING`
- CORS origins loaded from `settings.cors_origins`, startup log shows active value
- `/ready` returns 503 when DB or vector extension is unavailable
- Test conftest skips (not fails) when Docker is unavailable

### Must NOT Have (Guardrails)
- **NO factory-boy** — Faker + plain functions only
- **NO python-slugify** — unused in Sprint 1
- **NO Langfuse init/tracing** — `app/observability/` stays untouched
- **NO embedding generation** during seed — no Gemini API calls, no `--with-embeddings` flag
- **NO auth middleware logic** — `get_current_user()` is a hardcoded dict return, ≤15 LOC total
- **NO request body/response body capture** in middleware — method + path + status_code + duration_ms only
- **NO modifications to Sprint 2–5 directories**: `app/tools/`, `app/orchestrator/`, `app/reasoning/`, `app/voice/`, `app/memory/`, `app/evaluation/`
- **NO `create_all()` shortcut** — tests run `alembic upgrade head`, not `Base.metadata.create_all()`
- **NO auto-increment integer IDs in seed data** — use `uuid4()` for all seed row PKs
- **NO more than 12 markdown docs per vector collection** (keep seed tractable)
- **NO AI slop**: no gratuitous comments, no over-abstraction, no generic variable names (`data`, `result`, `item`)

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: NO (adding it in this sprint)
- **Automated tests**: YES — tests-after (not TDD for foundation work)
- **Framework**: pytest + pytest-asyncio (asyncio_mode=auto already in pyproject.toml)
- **Testcontainers**: `testcontainers[postgres]` with `pgvector/pgvector:0.8.0-pg16` image; skip if Docker unavailable

### QA Policy
Every task includes agent-executed QA scenarios. Evidence saved to `.omo/evidence/task-{N}-{slug}.{ext}`.

- **DB/Alembic**: Bash (psql + alembic CLI)
- **API**: Bash (curl)
- **Python modules**: Bash (python -c one-liners)
- **Tests**: Bash (pytest)

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — infrastructure + config, no dependencies):
├── Task 1: Docker Compose (Postgres 16 + pgvector) [quick]
├── Task 2: pyproject.toml deps (psycopg, faker, testcontainers) [quick]
└── Task 3: Settings (5 new fields + .env.example) [quick]

Wave 2 (After Wave 1 — schema, migration, retrieval, app surface):
├── Task 4: ORM models in app/db/models.py [unspecified-high]
├── Task 5a: Alembic init + env.py (async, register_vector) [unspecified-high]
└── Task 5b (After Task 4 + 5a): Two migrations + round-trip test [unspecified-high]

Wave 3 (After Wave 2 — everything consumes the schema):
├── Task 6: VectorStore wrapper + register_vector hook [unspecified-high]
├── Task 7: FastAPI surface (/ready, structlog, CORS, middleware, mock-auth stub) [unspecified-high]
└── Task 8: Synthetic data generator + seed CLI (merged) [unspecified-high]

Wave FINAL (After ALL tasks — 4 parallel reviews):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real QA — full DoD checklist (unspecified-high)
└── Task F4: Scope fidelity check (deep)
→ Present results → Get explicit user okay

Critical Path: Task 2 → Task 3 → Task 4 → Task 5a → Task 5b → Task 6 → Task 8 → Task 9 → F1–F4
Note: Tasks 1, 2, 3 run in parallel (Wave 1). The longest sequential chain starts at 2 (not 1).
Parallel Speedup: ~60% faster than sequential
Max Concurrent: 3 (Wave 1), 2 (Wave 2/3)
```

### Dependency Matrix

| Task | Depends On | Blocks |
|------|-----------|--------|
| 1 | — | 5b, 8, 9 |
| 2 | — | 3, 4, 6, 7, 8, 9 |
| 3 | 2 | 4, 6, 7, 8, 9 |
| 4 | 3 | 5b |
| 5a | 2, 3 | 5b |
| 5b | 1, 4, 5a | 6, 8, 9 |
| 6 | 3, 5b | 8, 9 |
| 7 | 3, 5b | 9 |
| 8 | 1, 3, 6 | 9 |
| 9 | 2, 5b, 6, 7, 8 | F1–F4 |
| 10 | 1, 2, 3, 4, 5b, 6, 7, 8 | F3 |

### Agent Dispatch Summary

- **Wave 1**: 3 tasks → `quick`, `quick`, `quick`
- **Wave 2**: 3 tasks → `unspecified-high`, `unspecified-high`, `unspecified-high` (5b after 4+5a)
- **Wave 3**: 3 tasks → `unspecified-high`, `unspecified-high`, `unspecified-high`
- **Wave 4 (Tests + Docs)**: 2 tasks → `unspecified-high` (Task 9), `writing` (Task 10)
- **FINAL**: 4 tasks → `oracle`, `unspecified-high`, `unspecified-high`, `deep`

---

## TODOs

> FORMAT: Labels use bare numbers `1.`, `2.`, etc. Final Wave uses `F1.`, `F2.`, etc.
> Every task is implementation + verification in one. No task touches Sprint 2–5 packages.

---

- [x] 1. docker/docker-compose.yml: Create Postgres 16 + pgvector Docker Compose service — enables local DB for all subsequent tasks

  **What to do**:
  - Create `docker/docker-compose.yml` with a single `db` service using image `pgvector/pgvector:0.8.0-pg16`
  - Port `5432:5432`, named volume `eva_pgdata`, restart policy `unless-stopped`
  - Environment variables: `POSTGRES_USER=eva`, `POSTGRES_PASSWORD=eva`, `POSTGRES_DB=eva` (read from `.env` via `env_file: .env`)
  - Healthcheck: `pg_isready -U eva -d eva` with `interval: 5s`, `timeout: 3s`, `retries: 5`
  - Create `docker/postgres/init.sql` containing only: `CREATE EXTENSION IF NOT EXISTS vector;`
  - Mount `./docker/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql:ro`
  - Docker Compose version: use `services:` without a top-level `version:` key (Compose V2)

  **Must NOT do**:
  - Do NOT add any other services (Redis, pgAdmin, Gemini proxy, etc.)
  - Do NOT use plain `postgres:16` image — must be `pgvector/pgvector:0.8.0-pg16`
  - Do NOT hardcode credentials — always read from `.env` via env_file

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single YAML file + one SQL file. No logic, no imports, pure config.
  - **Skills**: none
  - **Skills Evaluated but Omitted**:
    - `playwright`: no UI work
    - `fastapi`: no Python code

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3)
  - **Blocks**: Tasks 5b (DB must exist before migration round-trip), 8 (seed reads from live DB), 9 (tests need live DB)
  - **Blocked By**: None — can start immediately

  **References**:

  **Pattern References**:
  - `.env.example` — existing env var names (DATABASE_URL, POSTGRES_USER pattern)

  **External References**:
  - Docker Compose V2 reference: https://docs.docker.com/compose/compose-file/
  - pgvector Docker image: https://hub.docker.com/r/pgvector/pgvector

  **WHY Each Reference Matters**:
  - `.env.example` defines `DATABASE_URL=postgresql+asyncpg://eva:eva@localhost:5432/eva` — the user/password/db names (eva/eva/eva) come from there; the compose file must match

  **Acceptance Criteria**:

  ```
  Scenario: Docker stack starts and pgvector extension is active
    Tool: Bash
    Preconditions: Docker Desktop running, port 5432 free
    Steps:
      1. docker compose -f docker/docker-compose.yml up -d
      2. sleep 5  # wait for healthcheck
      3. docker compose -f docker/docker-compose.yml exec db psql -U eva -d eva -c "SELECT extname FROM pg_extension WHERE extname='vector';"
    Expected Result: Query returns 1 row with extname='vector', exit code 0
    Failure Indicators: "could not connect", "extension does not exist"
    Evidence: .omo/evidence/task-1-pgvector-active.txt

  Scenario: Clean teardown
    Tool: Bash
    Preconditions: Stack is running
    Steps:
      1. docker compose -f docker/docker-compose.yml down -v
    Expected Result: Exit code 0, volume eva_pgdata removed
    Failure Indicators: non-zero exit, orphan volume warnings
    Evidence: .omo/evidence/task-1-teardown.txt
  ```

  **Evidence to Capture**:
  - [ ] task-1-pgvector-active.txt — psql output showing vector extension row
  - [ ] task-1-teardown.txt — docker compose down output

  **Commit**: YES (groups with Task 2)
  - Message: `chore(infra): add Docker Compose with Postgres 16 + pgvector`
  - Files: `docker/docker-compose.yml`, `docker/postgres/init.sql`
  - Pre-commit: none (no Python code)

---

- [x] 2. pyproject.toml: Add missing runtime and dev dependencies for Alembic sync driver + test infrastructure

  **What to do**:
  - Add to `[project.dependencies]` (runtime):
    - `psycopg[binary]>=3.2` — Alembic sync driver (replaces asyncpg for migration connections)
    - `faker>=25` — synthetic data generation
  - Add to `[project.optional-dependencies] dev` (dev only):
    - `testcontainers[postgres]>=4.8` — hermetic CI testing
  - Run `uv sync --extra dev` to verify installation
  - Do NOT add `factory-boy`, `python-slugify`, or any other library

  **Must NOT do**:
  - Do NOT add `factory-boy` or `python-slugify`
  - Do NOT modify `ruff`, `mypy`, `pytest-asyncio`, or other existing dev tools
  - Do NOT add `faker` to dev-only — it's needed at runtime for the seed CLI

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: TOML file edits + one verification command.
  - **Skills**: none

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3)
  - **Blocks**: Tasks 3, 4, 6, 7, 8, 9 (all import new packages)
  - **Blocked By**: None — can start immediately

  **References**:

  **Pattern References**:
  - `pyproject.toml:9-40` — existing dependency format to match (`"package>=version"`)

  **WHY Each Reference Matters**:
  - Match existing format exactly — no `~=` or `^` specifiers, use `>=` only

  **Acceptance Criteria**:

  ```
  Scenario: New packages install without conflicts
    Tool: Bash
    Preconditions: Clean venv
    Steps:
      1. uv sync --extra dev
      2. uv run python -c "import psycopg, faker, testcontainers; print('ok')"
    Expected Result: Prints "ok", exit code 0
    Failure Indicators: ImportError, version conflict in uv output
    Evidence: .omo/evidence/task-2-imports.txt
  ```

  **Evidence to Capture**:
  - [ ] task-2-imports.txt — python -c output showing "ok"

  **Commit**: YES (groups with Task 1)
  - Message: `chore(deps): add psycopg, faker, testcontainers`
  - Files: `pyproject.toml`, `uv.lock`
  - Pre-commit: `uv sync --extra dev`

---

- [x] 3. app/config/settings.py: Add 5 Sprint 1 settings fields and update .env.example in lockstep

  **What to do**:
  - Add these fields to the `Settings` class in `app/config/settings.py`:
    ```python
    # Vector store tunables
    embedding_dim: int = 768                                      # Gemini text-embedding-004 dimensionality
    vector_index_type: Literal["hnsw", "ivfflat"] = "hnsw"
    hnsw_m: int = 16
    hnsw_ef_construction: int = 64

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # Auth (Sprint 1 stub)
    mock_auth_enabled: bool = True
    ```
  - Add matching entries to `.env.example`:
    ```
    # --- Vector store ---
    EMBEDDING_DIM=768
    VECTOR_INDEX_TYPE=hnsw
    HNSW_M=16
    HNSW_EF_CONSTRUCTION=64

    # --- CORS ---
    CORS_ORIGINS=["http://localhost:3000"]

    # --- Auth (Sprint 1 stub) ---
    MOCK_AUTH_ENABLED=true
    ```
  - The `lru_cache` on `get_settings()` already exists — do NOT remove it
  - `Literal` is already imported from `typing` — just add `"ivfflat"` if not present

  **Must NOT do**:
  - Do NOT add Sprint 2+ settings (chunk_size, rerank_top_k, max_context_length, etc.)
  - Do NOT change the LRU cache or model_config
  - Do NOT rename existing fields

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small targeted additions to one Settings class + one example file.
  - **Skills**: none

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2)
  - **Blocks**: Tasks 4, 6, 7, 8, 9 (all consume settings)
  - **Blocked By**: Task 2 (psycopg import check is unrelated but logically ordered)

  **References**:

  **Pattern References**:
  - `app/config/settings.py:14-57` — existing field format, type annotations, Field() usage

  **Acceptance Criteria**:

  ```
  Scenario: New settings load with correct defaults
    Tool: Bash
    Steps:
      1. uv run python -c "from app.config.settings import get_settings; s=get_settings(); assert s.embedding_dim==768; assert s.vector_index_type=='hnsw'; assert s.mock_auth_enabled is True; assert s.cors_origins==['http://localhost:3000']; print('ok')"
    Expected Result: Prints "ok", exit code 0
    Failure Indicators: AssertionError, ImportError
    Evidence: .omo/evidence/task-3-settings.txt

  Scenario: Settings override via environment variable
    Tool: Bash
    Steps:
      1. EMBEDDING_DIM=512 uv run python -c "from app.config.settings import Settings; s=Settings(); assert s.embedding_dim==512; print('override ok')"
    Expected Result: Prints "override ok"
    Failure Indicators: AssertionError (still 768)
    Evidence: .omo/evidence/task-3-settings-override.txt
  ```

  **Evidence to Capture**:
  - [ ] task-3-settings.txt — defaults assertion output
  - [ ] task-3-settings-override.txt — override assertion output

  **Commit**: YES (standalone)
  - Message: `feat(config): add vector, cors, mock-auth settings fields`
  - Files: `app/config/settings.py`, `.env.example`
  - Pre-commit: none

---

- [x] 4. app/db/models.py: Create 9 ORM models (8 relational + 1 vector) + TimestampMixin + update __init__.py

  **What to do**:
  - Create `app/db/models.py` with the following structure:
    ```
    TimestampMixin: created_at (DateTime, server_default=now(), onupdate), updated_at (same)
    
    Customer(TimestampMixin): id (UUID PK), email (unique, indexed), name, phone, company, plan_tier, is_active
    Subscription(TimestampMixin): id (UUID PK), customer_id (FK→customers.id ON DELETE CASCADE), plan_name, status, start_date, end_date, monthly_amount
    BillingRecord(TimestampMixin): id (UUID PK), customer_id (FK), subscription_id (FK), amount, currency, status, due_date (indexed), paid_at, description
    SupportTicket(TimestampMixin): id (UUID PK), customer_id (FK), title, description, status (indexed), priority, category, assigned_to, resolved_at
    UsageAnalytic(TimestampMixin): id (UUID PK), customer_id (FK), metric_name, metric_value, period_start, period_end
    CRMNote(TimestampMixin): id (UUID PK), customer_id (FK), author, content, note_type
    ConversationSession(TimestampMixin): id (UUID PK), customer_id (FK, indexed), session_status, language, summary, tools_used (JSONB)
    ConversationMessage(TimestampMixin): id (UUID PK), session_id (FK→conversation_sessions.id ON DELETE CASCADE), role (Enum: user|assistant|system), content, tool_calls (JSONB), token_count
    KnowledgeDocument: id (UUID PK), collection (Enum: documentation|policies|knowledge_articles|troubleshooting_guides), title, content (Text), source_ref, metadata_ (JSONB, name mapped to metadata), embedding (Vector(settings.embedding_dim))
    ```
  - Use `pgvector.sqlalchemy.Vector` for the embedding column
  - All FKs use `ondelete="CASCADE"` where appropriate
  - All PKs use `server_default=text("gen_random_uuid()")` (Postgres built-in)
  - Add HNSW index on `KnowledgeDocument.embedding` — but do NOT add this index in the model definition; it goes in migration 2 (Task 5b). The model just declares the column.
  - Add targeted `Index(...)` objects for: `customers.email` (already unique, skip), `support_tickets.status`, `billing_records.due_date`, `conversation_sessions.customer_id`
  - Re-export ALL model classes from `app/db/__init__.py` with `__all__` so Alembic's `target_metadata = Base.metadata` picks them up

  **Must NOT do**:
  - Do NOT put the HNSW index inside the model `__table_args__` — it belongs in migration 2
  - Do NOT use `Integer` auto-increment PKs — use UUID with server_default
  - Do NOT import from Sprint 2–5 packages

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Complex multi-model ORM file with relationships, custom types (pgvector), mixins, and careful UUID/FK patterns.
  - **Skills**: none
  - **Skills Evaluated but Omitted**:
    - `quick`: too complex for quick — 9 models, TimestampMixin, pgvector column, careful FK/index setup

  **Parallelization**:
  - **Can Run In Parallel**: YES (alongside Task 5a)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 5b (autogenerate reads models)
  - **Blocked By**: Tasks 2, 3 (pgvector installed; settings.embedding_dim available)

  **References**:

  **Pattern References**:
  - `app/db/session.py:20` — `class Base(DeclarativeBase)` — extend this class
  - `app/db/__init__.py:1-16` — existing re-export pattern to follow for model additions

  **API/Type References**:
  - `pgvector.sqlalchemy.Vector` — column type for embeddings
  - SQLAlchemy 2.x `Mapped[T]` + `mapped_column()` API (not the legacy `Column()` API)

  **External References**:
  - pgvector SQLAlchemy integration: https://github.com/pgvector/pgvector-python#sqlalchemy
  - SQLAlchemy 2.x declarative mapping: https://docs.sqlalchemy.org/en/20/orm/mapping_styles.html#declarative-mapping

  **WHY Each Reference Matters**:
  - Must use SQLAlchemy 2.x `Mapped[T]` syntax (the project is on SQLAlchemy 2.x per pyproject.toml) — the old `Column()` API works but produces deprecation warnings and is inconsistent with the existing `Base`
  - pgvector-python README shows exactly how to declare `Vector(dim)` with SQLAlchemy 2.x mapped_column

  **Acceptance Criteria**:

  ```
  Scenario: All 9 tables discoverable via Base.metadata
    Tool: Bash
    Steps:
      1. uv run python -c "from app.db import Base, Customer, KnowledgeDocument; tables = sorted(Base.metadata.tables.keys()); expected = ['billing_records','conversation_messages','conversation_sessions','crm_notes','customers','knowledge_documents','subscriptions','support_tickets','usage_analytics']; assert tables == expected, tables; print('ok')"
    Expected Result: Prints "ok"
    Failure Indicators: AssertionError with missing/extra table names
    Evidence: .omo/evidence/task-4-tables.txt

  Scenario: KnowledgeDocument has Vector column of correct dimensionality
    Tool: Bash
    Steps:
      1. uv run python -c "from app.db.models import KnowledgeDocument; from pgvector.sqlalchemy import Vector; col = KnowledgeDocument.__table__.c.embedding; assert isinstance(col.type, Vector); assert col.type.dim == 768; print('vector ok')"
    Expected Result: Prints "vector ok"
    Failure Indicators: AttributeError, AssertionError
    Evidence: .omo/evidence/task-4-vector-col.txt
  ```

  **Evidence to Capture**:
  - [ ] task-4-tables.txt — 9 table names assertion
  - [ ] task-4-vector-col.txt — Vector(768) column assertion

  **Commit**: YES (standalone)
  - Message: `feat(db): add ORM models for all 9 EVA tables`
  - Files: `app/db/models.py`, `app/db/__init__.py`
  - Pre-commit: `uv run python -c "from app.db import Base; print(list(Base.metadata.tables))"`

---

- [x] 5. migrations/: Alembic async init + env.py configuration + two sequential migrations (tables → HNSW index)

  **What to do**:

  **Part A — Alembic init and env.py**:
  - Run `uv run alembic init -t async migrations`
  - Edit `alembic.ini`: set `script_location = migrations` (already default), set `sqlalchemy.url = ` (blank — will be set programmatically)
  - Edit `migrations/env.py`:
    - Import `Base` and all models from `app.db` (this populates `Base.metadata`)
    - Import `get_settings` from `app.config`
    - Build the **sync** database URL by replacing `+asyncpg` with `+psycopg` in `settings.database_url`
    - Set `target_metadata = Base.metadata`
    - In `run_migrations_online()`, use `connectable = create_engine(sync_url)` + `connection.run_sync(do_run_migrations)`
    - Register pgvector type in `run_migrations_online()`: after creating the connection, call `pgvector.psycopg.register_vector(connection)` (psycopg3 sync registration)
    - Do NOT use `AsyncEngine.run_sync` — Alembic online mode must use a synchronous engine

  **Part B — First migration (extension + 9 tables)**:
  - Run `uv run alembic revision --autogenerate -m "init_schema"`
  - Manually edit the generated revision to add at the **top of `upgrade()`**:
    ```python
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    ```
  - Verify autogenerate captured all 9 tables and FKs
  - Ensure the `downgrade()` drops tables in FK-safe reverse order

  **Part C — Second migration (HNSW index on knowledge_documents.embedding)**:
  - Run `uv run alembic revision -m "add_hnsw_index"` (manual, not autogenerate)
  - In `upgrade()`:
    ```python
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_knowledge_documents_embedding_hnsw
        ON knowledge_documents
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    ```
  - In `downgrade()`:
    ```python
    op.execute("DROP INDEX IF EXISTS ix_knowledge_documents_embedding_hnsw")
    ```
  - Note: `CONCURRENTLY` requires being outside a transaction — add `connection.execute(text("COMMIT"))` before the HNSW create, then restart a transaction after. Or use `op.get_bind().execute()` outside the default transaction block. Simplest: use `op.execute()` with `execution_options={"isolation_level": "AUTOCOMMIT"}` via `with op.get_context().bind.connect() as conn: conn.execution_options(isolation_level="AUTOCOMMIT").execute(...)`.

  **Part D — Round-trip test**:
  - `uv run alembic upgrade head`
  - `uv run alembic downgrade -1` (drops HNSW index)
  - `uv run alembic upgrade head` (re-creates it)
  - Then `uv run alembic downgrade base` → `uv run alembic upgrade head` (full round-trip)
  - `uv run alembic current` — should show head at second migration

  **Must NOT do**:
  - Do NOT put HNSW index creation in migration 1 — it must be migration 2
  - Do NOT use `Base.metadata.create_all()` anywhere — Alembic is the only DDL source of truth
  - Do NOT use async engine in env.py — Alembic requires synchronous connections

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Multi-step Alembic configuration with pgvector-specific sync/async engine split, register_vector hook, and manual HNSW migration requiring AUTOCOMMIT execution.
  - **Skills**: none

  **Parallelization**:
  - **Can Run In Parallel**: Part A can run in parallel with Task 4 (Wave 2). Parts B+C+D must wait for Task 4 (models must exist for autogenerate).
  - **Parallel Group**: Wave 2 — Task 5 Part A alongside Task 4; Parts B/C/D after Task 4 completes
  - **Blocks**: Tasks 6, 8, 9 (all need the schema to exist)
  - **Blocked By**: Tasks 1 (DB must be running for round-trip), 2 (psycopg installed), 3 (settings available), 4 (models define target_metadata)

  **References**:

  **Pattern References**:
  - `app/db/session.py:28-41` — `create_async_engine` pattern to mirror in sync for Alembic
  - `app/db/__init__.py` — import path for Base + all models

  **External References**:
  - Alembic async guide: https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic
  - pgvector-python psycopg registration: https://github.com/pgvector/pgvector-python#psycopg-3
  - HNSW CONCURRENTLY in migration: https://github.com/pgvector/pgvector?tab=readme-ov-file#indexing

  **WHY Each Reference Matters**:
  - Alembic async cookbook shows the exact `run_sync` pattern — Alembic does NOT use asyncio internally
  - pgvector-python registration: psycopg3 uses `register_vector(conn)` not `register_vector_async` in sync context
  - HNSW CONCURRENTLY requires AUTOCOMMIT — the pgvector README explains this constraint

  **Acceptance Criteria**:

  ```
  Scenario: Full migration round-trip succeeds
    Tool: Bash
    Preconditions: Docker Compose DB running, Task 4 models exist
    Steps:
      1. uv run alembic upgrade head
      2. uv run alembic current  # should show (head)
      3. uv run alembic downgrade base
      4. uv run alembic upgrade head
    Expected Result: All commands exit 0; "current" shows (head) at migration 2
    Failure Indicators: "can't locate revision", "no such table", non-zero exit
    Evidence: .omo/evidence/task-5-round-trip.txt

  Scenario: All 9 tables + HNSW index exist post-migration
    Tool: Bash
    Steps:
      1. docker compose -f docker/docker-compose.yml exec db psql -U eva -d eva -c "\dt"
      2. docker compose -f docker/docker-compose.yml exec db psql -U eva -d eva -c "\di ix_knowledge_documents_embedding_hnsw"
    Expected Result: \dt shows 10 rows (9 tables + alembic_version); \di shows the HNSW index
    Failure Indicators: "Did not find any relation" for index
    Evidence: .omo/evidence/task-5-schema.txt
  ```

  **Evidence to Capture**:
  - [ ] task-5-round-trip.txt — alembic upgrade/downgrade/upgrade output
  - [ ] task-5-schema.txt — psql \dt and \di output

  **Commit**: YES (standalone)
  - Message: `feat(db): Alembic async setup + init schema + HNSW index migrations`
  - Files: `alembic.ini`, `migrations/env.py`, `migrations/script.py.mako`, `migrations/versions/*.py`
  - Pre-commit: `uv run alembic upgrade head`

---

- [x] 6. app/retrieval/vector_store.py: VectorStore class + register_vector hook on async engine

  **What to do**:

  **Part A — register_vector on async engine**:
  - In `app/db/session.py`, add after `create_async_engine(...)`:
    ```python
    from sqlalchemy import event
    import pgvector.asyncpg

    @event.listens_for(engine.sync_engine, "connect")
    def _on_connect(dbapi_conn, connection_record):
        pgvector.asyncpg.register_vector(dbapi_conn)
    ```
  - Also add a `reset_engine()` function for test teardown:
    ```python
    def reset_engine() -> None:
        """Reset engine singletons — call in test teardown to allow re-init with new settings."""
        global _engine, _session_factory
        _engine = None
        _session_factory = None
    ```
  - Update `app/db/__init__.py` to export `reset_engine`

  **Part B — Pydantic schemas in app/schemas/vector.py**:
  - Create `app/schemas/vector.py` with:
    ```python
    class VectorItem(BaseModel):
        id: str           # unique within collection
        collection: str
        title: str
        content: str
        source_ref: str = ""
        metadata: dict = {}
        embedding: list[float]  # must be len == settings.embedding_dim

    class SearchResult(BaseModel):
        id: str
        collection: str
        title: str
        content: str
        source_ref: str
        metadata: dict
        score: float      # cosine similarity score (0.0 – 1.0, higher = more similar)
    ```

  **Part C — VectorStore class in app/retrieval/vector_store.py**:
  - `class VectorStore` with `__init__(self, session_factory=None)` — defaults to `get_session_factory()`
  - Methods (all async):
    - `async def upsert(self, items: list[VectorItem]) -> int` — bulk insert via `INSERT INTO knowledge_documents (...) VALUES ... ON CONFLICT (id) DO UPDATE SET ...`; return number of rows upserted
    - `async def search(self, collection: str, query_embedding: list[float], top_k: int = 5) -> list[SearchResult]` — raw SQL with `ORDER BY embedding <=> CAST(:q AS vector) LIMIT :k`; compute score as `1 - distance`
    - `async def delete(self, collection: str, ids: list[str]) -> int` — DELETE WHERE id IN (...); return rows deleted
    - `async def count(self, collection: str) -> int` — COUNT(*) for collection
    - `async def truncate(self, collection: str) -> None` — DELETE WHERE collection = :c (NOT DROP TABLE)
  - Use `sqlalchemy.text(...)` for all queries — no ORM query API in VectorStore (performance + clarity)
  - Cast embedding parameter: `:q` cast as `CAST(:q AS vector)` in the ORDER BY clause

  **Must NOT do**:
  - Do NOT use ORM `.select()` / `.filter()` in VectorStore — use raw `text()` SQL
  - Do NOT add Sprint 2+ methods (rerank, hybrid_search, etc.)
  - Do NOT import from `app/tools/`, `app/orchestrator/`, etc.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Async SQLAlchemy raw SQL, pgvector register_vector hook, custom cosine distance query, Pydantic schema design.
  - **Skills**: none

  **Parallelization**:
  - **Can Run In Parallel**: YES (alongside Tasks 7, 8 — they have separate concerns)
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 8 (seed uses VectorStore), Task 9 (tests validate VectorStore)
  - **Blocked By**: Tasks 3 (settings.embedding_dim), 5 (schema with knowledge_documents table)

  **References**:

  **Pattern References**:
  - `app/db/session.py:28-54` — `get_engine()`, `get_session_factory()` — hook onto the engine returned here
  - `app/db/session.py:57-66` — `get_db_session()` dependency pattern — VectorStore follows the same session lifecycle

  **API/Type References**:
  - `app/db/models.py:KnowledgeDocument` — table columns to match in raw SQL INSERT
  - `app/schemas/vector.py:VectorItem, SearchResult` — input/output types

  **External References**:
  - pgvector cosine distance SQL: https://github.com/pgvector/pgvector#querying
  - pgvector asyncpg registration: https://github.com/pgvector/pgvector-python#asyncpg

  **WHY Each Reference Matters**:
  - `embedding <=> CAST(:q AS vector)` is the cosine distance operator — must use `<=>` not `<->` (which is L2)
  - `pgvector.asyncpg.register_vector(dbapi_conn)` must be called before any vector query — the connect hook ensures it fires for every new connection in the pool

  **Acceptance Criteria**:

  ```
  Scenario: Vector roundtrip — upsert then search returns same item
    Tool: Bash
    Preconditions: DB running with migrations applied
    Steps:
      1. uv run python -c "
  import asyncio, random
  from app.retrieval.vector_store import VectorStore
  from app.schemas.vector import VectorItem

  async def test():
      vs = VectorStore()
      item = VectorItem(id='test-001', collection='documentation', title='Test Doc',
                        content='Test content', embedding=[random.random() for _ in range(768)])
      await vs.upsert([item])
      results = await vs.search('documentation', item.embedding, top_k=1)
      assert len(results) == 1
      assert results[0].id == 'test-001'
      assert results[0].score > 0.99
      await vs.delete('documentation', ['test-001'])
      count = await vs.count('documentation')
      print(f'count after delete: {count}')

  asyncio.run(test())
  "
    Expected Result: Prints "count after delete: 0", no exception
    Failure Indicators: Exception, count != 0, score < 0.99
    Evidence: .omo/evidence/task-6-roundtrip.txt

  Scenario: register_vector hook prevents asyncpg vector type error
    Tool: Bash
    Steps:
      1. uv run python -c "
  import asyncio
  from app.db import get_db_session
  from sqlalchemy import text

  async def test():
      async with get_db_session() as session:
          result = await session.execute(text('SELECT embedding FROM knowledge_documents LIMIT 1'))
          print('no type error')

  asyncio.run(test())
  "
    Expected Result: Prints "no type error" (even if no rows exist)
    Failure Indicators: "cannot adapt type NoneType", asyncpg.exceptions.UndefinedObjectError
    Evidence: .omo/evidence/task-6-hook.txt
  ```

  **Evidence to Capture**:
  - [ ] task-6-roundtrip.txt — full roundtrip assertion output
  - [ ] task-6-hook.txt — no vector type error

  **Commit**: YES (standalone)
  - Message: `feat(retrieval): VectorStore with cosine search + register_vector hook`
  - Files: `app/retrieval/vector_store.py`, `app/schemas/vector.py`, `app/db/session.py` (hook + reset_engine), `app/db/__init__.py`
  - Pre-commit: `uv run python -c "from app.retrieval.vector_store import VectorStore; print('ok')"`

---

- [x] 7. app/main.py + app/api/deps.py: /ready endpoint, structlog config, CORS from settings, request-log middleware, mock-auth stub

  **What to do**:

  **Part A — structlog configuration in lifespan**:
  - In `app/main.py` `lifespan()`, add structlog configuration before `yield`:
    ```python
    import structlog
    processors = [structlog.contextvars.merge_contextvars, structlog.processors.add_log_level,
                  structlog.processors.TimeStamper(fmt="iso")]
    if settings.environment != "development":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    structlog.configure(processors=processors, wrapper_class=structlog.make_filtering_bound_logger(logging.INFO))
    log = structlog.get_logger()
    log.info("EVA backend starting", environment=settings.environment,
             cors_origins=settings.cors_origins)  # MUST log CORS origins on startup
    ```

  **Part B — CORS from settings**:
  - In `create_app()`, replace `allow_origins=["*"]` with `allow_origins=settings.cors_origins`

  **Part C — Request-log middleware**:
  - Add `@app.middleware("http")` in `create_app()`:
    ```python
    import time
    @app.middleware("http")
    async def request_log(request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        structlog.get_logger().info("request", method=request.method,
                                    path=request.url.path,
                                    status_code=response.status_code,
                                    duration_ms=duration_ms)
        return response
    ```

  **Part D — /ready endpoint**:
  - Add a new route in `create_app()` (or a mini-router at `app/api/routers/meta.py`):
    ```python
    @app.get("/ready", tags=["meta"])
    async def ready(session: AsyncSession = Depends(get_db_session)) -> dict:
        try:
            await session.execute(text("SELECT 1"))
            result = await session.execute(text("SELECT extname FROM pg_extension WHERE extname='vector'"))
            vector_ok = result.scalar() == "vector"
        except Exception:
            raise HTTPException(status_code=503, detail={"status": "not ready", "db": False, "vector": False})
        if not vector_ok:
            raise HTTPException(status_code=503, detail={"status": "not ready", "db": True, "vector": False})
        return {"status": "ready", "db": True, "vector": True}
    ```

  **Part E — Mock-auth stub (app/api/deps.py)**:
  - Create `app/api/deps.py` with exactly this content (≤15 LOC):
    ```python
    """FastAPI dependency stubs. Sprint 1: mock-only. Sprint 2 will implement real auth."""
    from fastapi import HTTPException
    from app.config import get_settings

    async def get_current_user() -> dict:
        settings = get_settings()
        if not settings.mock_auth_enabled:
            raise HTTPException(status_code=401, detail="Authentication not configured")
        return {"customer_id": "mock_001", "name": "Mock User", "email": "mock@clouddesk.com"}
    ```
  - Do NOT wire `get_current_user` into any route in Sprint 1 (stub exists for Sprint 2 to import)

  **Must NOT do**:
  - Do NOT capture request body or response body in the middleware
  - Do NOT import from Sprint 2–5 packages
  - Do NOT add more than the 4 listed fields to the middleware log (method, path, status_code, duration_ms)
  - Do NOT add auth logic (token parsing, DB user lookup) to deps.py

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Multiple interconnected FastAPI patterns (middleware, lifespan, dependency injection, structlog configuration) in one file.
  - **Skills**: none

  **Parallelization**:
  - **Can Run In Parallel**: YES (alongside Tasks 6, 8 — no shared file edits in Wave 3)
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 9 (tests verify /ready, logging, CORS)
  - **Blocked By**: Tasks 3 (settings.cors_origins exists), 5 (DB + extension available for /ready)

  **References**:

  **Pattern References**:
  - `app/main.py:17-54` — existing lifespan, create_app, /health — extend these, do not rewrite
  - `app/db/session.py:57-66` — `get_db_session()` — inject this into /ready

  **External References**:
  - structlog configuration: https://www.structlog.org/en/stable/getting-started.html
  - FastAPI middleware: https://fastapi.tiangolo.com/tutorial/middleware/

  **WHY Each Reference Matters**:
  - `structlog.configure()` must be called once at app startup — lifespan is the right place
  - The existing `/health` route is already in `create_app()` — `/ready` should follow the same pattern inline (not a separate router file) to keep Sprint 1 simple

  **Acceptance Criteria**:

  ```
  Scenario: /ready returns 200 with correct JSON when DB is up
    Tool: Bash
    Preconditions: DB running, migrations applied
    Steps:
      1. uv run uvicorn app.main:app --reload &
      2. sleep 3
      3. curl -s http://localhost:8000/ready
    Expected Result: {"status":"ready","db":true,"vector":true} with HTTP 200
    Failure Indicators: 503, "connection refused", missing keys
    Evidence: .omo/evidence/task-7-ready.txt

  Scenario: /health still works (liveness, no DB call)
    Tool: Bash
    Steps:
      1. curl -s http://localhost:8000/health
    Expected Result: {"status":"ok","env":"development"} with HTTP 200
    Failure Indicators: 500, missing "env" key
    Evidence: .omo/evidence/task-7-health.txt

  Scenario: Mock-auth stub returns hardcoded user
    Tool: Bash
    Steps:
      1. uv run python -c "import asyncio; from app.api.deps import get_current_user; u=asyncio.run(get_current_user()); assert u['customer_id']=='mock_001'; print('auth stub ok')"
    Expected Result: Prints "auth stub ok"
    Failure Indicators: AssertionError, HTTPException
    Evidence: .omo/evidence/task-7-auth-stub.txt

  Scenario: CORS origins come from settings (not hardcoded *)
    Tool: Bash
    Steps:
      1. curl -s -I -H "Origin: http://localhost:3000" -H "Access-Control-Request-Method: GET" -X OPTIONS http://localhost:8000/ready
    Expected Result: Response headers contain "Access-Control-Allow-Origin: http://localhost:3000"
    Failure Indicators: Header absent, "null" value
    Evidence: .omo/evidence/task-7-cors.txt
  ```

  **Evidence to Capture**:
  - [ ] task-7-ready.txt — /ready JSON response
  - [ ] task-7-health.txt — /health JSON response
  - [ ] task-7-auth-stub.txt — auth stub assertion
  - [ ] task-7-cors.txt — CORS response headers

  **Commit**: YES (standalone)
  - Message: `feat(api): /ready endpoint, structlog, CORS from settings, request-log middleware, auth stub`
  - Files: `app/main.py`, `app/api/deps.py`
  - Pre-commit: `uv run python -c "from app.main import app; print('ok')"`

---

- [x] 8. scripts/seed_db.py + scripts/generate_synthetic_data.py + data/synthetic/: Faker-based idempotent seed + 50-scenario JSONL + 48 markdown docs

  **What to do**:

  **Part A — Synthetic data generator (scripts/generate_synthetic_data.py)**:
  - `python -m scripts.generate_synthetic_data --seed 42 --out data/synthetic` 
  - Uses `Faker(locale="en_US", seed_instance=42)` — no factory-boy
  - Produces `data/synthetic/eval_scenarios.jsonl` — 50 JSON lines, 10 per category:
    - Categories: `Billing`, `Subscription`, `Refund`, `Product`, `Account Access`
    - Each line schema:
      ```json
      {"id": "eval-001", "category": "Billing", "user_utterance": "...", 
       "expected_intent": "billing_inquiry", "expected_tool": "get_billing_history",
       "expected_slots": {"customer_id": "mock_001"}, 
       "ground_truth_answer_keywords": ["charge", "invoice", "amount"]}
      ```
  - Produces `data/synthetic/docs/{collection}/*.md` — 12 files per collection:
    - Collections: `documentation`, `policies`, `knowledge_articles`, `troubleshooting_guides`
    - Each MD file: realistic CloudDesk CRM content (subscription management, billing policies, refund windows, troubleshooting steps)
    - File naming: `{collection}/{nn}-{kebab-title}.md` (use f-string, no python-slugify needed)
    - Each file ≥ 200 words of realistic content
  - Generator must be reproducible: same seed = identical output every run

  **Part B — Seed CLI (scripts/seed_db.py)**:
  - `python -m scripts.seed_db [--reset]`
  - On first run: count rows in `customers`. If >0 and `--reset` not passed → log "Database already seeded. Use --reset to re-seed." and exit 0.
  - With `--reset` or empty DB: truncate all 8 relational tables in FK-safe order, then insert:
    - 20 customers (uuid PKs, unique emails)
    - 30 subscriptions (FK → customers, varied statuses: active/inactive/trial/cancelled)
    - 90 billing records (FK → customers + subscriptions, varied statuses, some overdue)
    - 40 support tickets (FK → customers, mix of statuses/priorities/categories)
    - 200 usage analytics rows (FK → customers, varied metric names)
    - 30 CRM notes (FK → customers, varied note types)
    - 25 conversation sessions (FK → customers, varied languages: en/bn)
    - 100 conversation messages (FK → sessions, role in user|assistant|system)
  - All inserts via `session.execute(insert(Model).values([...]).on_conflict_do_nothing(index_elements=["id"]))`
  - Use `Faker(seed=42)` — no factory-boy
  - Print final counts per table after seeding
  - **NO embedding generation** — `knowledge_documents` table is NOT seeded by this script; that's Sprint 2 when VectorStore is used for retrieval

  **Must NOT do**:
  - Do NOT import or use factory-boy
  - Do NOT call Gemini API or generate embeddings
  - Do NOT add a `--with-embeddings` flag
  - Do NOT use `python-slugify` — use simple f-string formatting
  - Do NOT seed `knowledge_documents` table (no embeddings in Sprint 1)
  - Do NOT generate more than 12 markdown files per collection

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Two interdependent scripts with Faker data generation, async SQLAlchemy bulk inserts, FK ordering, and markdown file writing. Complex but well-scoped.
  - **Skills**: none

  **Parallelization**:
  - **Can Run In Parallel**: YES (alongside Tasks 6, 7 in Wave 3)
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 9 (tests call seed_db, verify idempotency)
  - **Blocked By**: Tasks 1 (DB running), 3 (settings), 4 (ORM models for type hints), 5 (schema applied to DB), 6 (no direct dependency but logically after VectorStore exists)

  **References**:

  **Pattern References**:
  - `app/db/models.py` — all model classes and their FK structure (must match insert order)
  - `app/db/session.py:44-54` — `get_session_factory()` — use this to create async sessions in seed

  **External References**:
  - Faker docs: https://faker.readthedocs.io/en/master/
  - SQLAlchemy bulk insert: https://docs.sqlalchemy.org/en/20/core/dml.html#insert-many-values

  **WHY Each Reference Matters**:
  - FK insert order is critical: customers → subscriptions → billing_records → support_tickets → usage_analytics → crm_notes → conversation_sessions → conversation_messages
  - `on_conflict_do_nothing(index_elements=["id"])` is the idempotency mechanism — models must have UUID PKs with unique constraint (confirmed in Task 4)

  **Acceptance Criteria**:

  ```
  Scenario: Generator produces correct output structure
    Tool: Bash
    Steps:
      1. uv run python -m scripts.generate_synthetic_data --seed 42 --out data/synthetic
      2. uv run python -c "import json; lines=open('data/synthetic/eval_scenarios.jsonl').readlines(); assert len(lines)==50; from collections import Counter; cats=Counter(json.loads(l)['category'] for l in lines); assert len(cats)==5; assert all(v==10 for v in cats.values()); print(dict(cats))"
      3. uv run python -c "import pathlib; docs=list(pathlib.Path('data/synthetic/docs').rglob('*.md')); assert len(docs)==48, len(docs); print('docs ok')"
    Expected Result: Prints category Counter (10 each), prints "docs ok"
    Failure Indicators: AssertionError, wrong counts
    Evidence: .omo/evidence/task-8-generator.txt

  Scenario: Seed CLI is idempotent (second run = no-op)
    Tool: Bash
    Preconditions: DB running with migrations applied
    Steps:
      1. uv run python -m scripts.seed_db
      2. uv run python -m scripts.seed_db
    Expected Result: Second run logs "Database already seeded" and exits 0; row counts unchanged
    Failure Indicators: UniqueViolation error, row counts increase on second run
    Evidence: .omo/evidence/task-8-idempotent.txt

  Scenario: Seed CLI --reset truncates and re-seeds
    Tool: Bash
    Steps:
      1. uv run python -m scripts.seed_db --reset
    Expected Result: All 8 tables have expected row counts; no FK errors
    Failure Indicators: ForeignKeyViolation, IntegrityError
    Evidence: .omo/evidence/task-8-reset.txt
  ```

  **Evidence to Capture**:
  - [ ] task-8-generator.txt — category counter + docs count
  - [ ] task-8-idempotent.txt — both seed runs output
  - [ ] task-8-reset.txt — reset run table counts

  **Commit**: YES (standalone)
  - Message: `feat(data): Faker-based synthetic data generator + idempotent seed CLI`
  - Files: `scripts/generate_synthetic_data.py`, `scripts/seed_db.py`, `data/synthetic/eval_scenarios.jsonl`, `data/synthetic/docs/**/*.md`
  - Pre-commit: `uv run python -m scripts.generate_synthetic_data --seed 42`

---

- [x] 9. tests/: pytest suite — conftest (testcontainers), 10+ tests covering all DoD items

  **What to do**:

  **tests/conftest.py** — session-scoped fixtures:
  ```python
  # Detects whether to use testcontainers or existing DATABASE_URL
  # If DATABASE_URL matches the default "localhost:5432", try testcontainers
  # If Docker is unavailable, pytest.skip("Docker unavailable") for DB-dependent tests
  # Uses pgvector/pgvector:0.8.0-pg16 image
  # After container starts: override DATABASE_URL in settings via monkeypatch (or env var)
  # Calls: alembic upgrade head (subprocess) once per session
  # Session-scoped engine; function-scoped db_session that rolls back after each test
  # Fixture: async_session (function-scoped) wraps get_db_session()
  # Fixture: reset_engine_fixture (function-scoped) calls reset_engine() in teardown
  ```

  **Test files to create**:

  `tests/test_health.py` — already exists (keep the 1 existing test, extend if needed)

  `tests/test_db_models.py`:
  - `test_all_9_tables_exist` — parameterized over 9 table names, queries information_schema
  - `test_knowledge_document_embedding_column_type` — checks column type is vector(768)
  - `test_timestamp_mixin_columns` — checks created_at/updated_at exist on Customer

  `tests/test_vector_store.py`:
  - `test_upsert_and_search_roundtrip` — insert deterministic 768-dim vector, search, assert score > 0.99
  - `test_cosine_distance_monotonicity` — insert 3 items with known distances, assert search rank order
  - `test_delete_removes_item` — upsert then delete, verify count drops
  - `test_count_by_collection` — multi-collection upsert, verify per-collection counts

  `tests/test_seed.py`:
  - `test_seed_first_run_populates_tables` — calls seed, asserts customer count == 20
  - `test_seed_second_run_is_noop` — calls seed twice, asserts count unchanged

  `tests/test_api.py`:
  - `test_health_returns_ok` — (existing) keep
  - `test_ready_returns_200_when_db_up` — TestClient /ready with live DB
  - `test_ready_auth_stub_exists` — imports get_current_user, runs it, checks customer_id key

  **Must NOT do**:
  - Do NOT use `Base.metadata.create_all()` in conftest — run `alembic upgrade head` via subprocess
  - Do NOT test Sprint 2–5 functionality
  - Do NOT add coverage thresholds as hard failures — report coverage but don't fail on < threshold
  - Do NOT write more than 15 test functions total

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Complex async pytest setup with testcontainers, session-scoped fixtures, Alembic subprocess call, and multiple test files.
  - **Skills**: none

  **Parallelization**:
  - **Can Run In Parallel**: NO — must run after ALL other tasks complete
  - **Parallel Group**: Wave 4 (final implementation task before Final Verification)
  - **Blocks**: F1–F4
  - **Blocked By**: All tasks 1–8 (tests validate everything)

  **References**:

  **Pattern References**:
  - `tests/test_health.py:1-14` — existing test structure and import pattern
  - `pyproject.toml:49-51` — `asyncio_mode = auto`, `testpaths = ["tests"]`
  - `app/db/session.py` — `reset_engine()` function added in Task 6 — call in fixture teardown

  **External References**:
  - testcontainers-python Postgres: https://testcontainers-python.readthedocs.io/en/latest/modules/postgres.html
  - pytest-asyncio: https://pytest-asyncio.readthedocs.io/en/latest/reference/fixtures.html

  **WHY Each Reference Matters**:
  - testcontainers with pgvector image must use `PostgresContainer(image="pgvector/pgvector:0.8.0-pg16")` — plain postgres image won't have the vector extension
  - `asyncio_mode = auto` already set — no `@pytest.mark.asyncio` decorators needed on async tests

  **Acceptance Criteria**:

  ```
  Scenario: Full test suite passes
    Tool: Bash
    Preconditions: Docker running (for testcontainers) OR existing DB at localhost:5432
    Steps:
      1. uv run pytest -q --cov=app --cov-report=term-missing
    Expected Result: ≥10 passed, 0 failed, coverage report visible
    Failure Indicators: FAILED tests, import errors, testcontainers timeout
    Evidence: .omo/evidence/task-9-pytest.txt

  Scenario: Vector store roundtrip test passes in isolation
    Tool: Bash
    Steps:
      1. uv run pytest tests/test_vector_store.py -v -q
    Expected Result: All vector tests pass
    Failure Indicators: asyncpg type errors, cosine distance assertion failures
    Evidence: .omo/evidence/task-9-vector-tests.txt

  Scenario: Second seed run produces no new rows (idempotency test)
    Tool: Bash
    Steps:
      1. uv run pytest tests/test_seed.py -v -q
    Expected Result: test_seed_second_run_is_noop passes
    Failure Indicators: Row count changed between calls
    Evidence: .omo/evidence/task-9-seed-tests.txt
  ```

  **Evidence to Capture**:
  - [ ] task-9-pytest.txt — full pytest output with coverage
  - [ ] task-9-vector-tests.txt — vector store test output
  - [ ] task-9-seed-tests.txt — seed idempotency test output

  **Commit**: YES (standalone)
  - Message: `test: pytest suite with testcontainers, vector roundtrip, seed idempotency`
  - Files: `tests/conftest.py`, `tests/test_db_models.py`, `tests/test_vector_store.py`, `tests/test_seed.py`, `tests/test_api.py`
  - Pre-commit: `uv run pytest -q`

---

- [x] 10. README.md + .env.example: Sprint 1 Quick Start section and complete env var documentation

  **What to do**:
  - Replace the existing Quick Start section in `README.md` with a complete step-by-step that a reviewer can follow on a fresh clone:
    ```
    1. Copy .env.example → .env
    2. docker compose -f docker/docker-compose.yml up -d
    3. uv sync --extra dev
    4. uv run alembic upgrade head
    5. uv run python -m scripts.generate_synthetic_data --seed 42
    6. uv run python -m scripts.seed_db
    7. uv run uvicorn app.main:app --reload
    8. curl http://localhost:8000/health → {"status":"ok"}
    9. curl http://localhost:8000/ready → {"status":"ready","db":true,"vector":true}
    10. uv run pytest -q → ≥10 passed
    ```
  - Add a "Sprint 1 Status" checklist mirroring the Definition of Done above
  - Document every new env var added by Task 3 (EMBEDDING_DIM, VECTOR_INDEX_TYPE, CORS_ORIGINS, MOCK_AUTH_ENABLED, HNSW_M, HNSW_EF_CONSTRUCTION)
  - Keep the existing Layout and Tooling sections — do NOT remove them
  - Update `.env.example` if any gaps are found between what Settings reads and what the example shows

  **Must NOT do**:
  - Do NOT add Langfuse setup steps to Quick Start (keys optional in Sprint 1)
  - Do NOT add frontend setup steps (Sprint 5)
  - Do NOT write more than 150 lines total to README

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: Pure documentation task — accurate, concise technical prose.
  - **Skills**: none

  **Parallelization**:
  - **Can Run In Parallel**: YES (alongside Task 9 — no file conflicts)
  - **Parallel Group**: Wave 4 (can draft in parallel with tests)
  - **Blocks**: F3 (reviewer follows README to reach green /ready)
  - **Blocked By**: Tasks 1–8 (README must reflect final state of all commands)

  **References**:

  **Pattern References**:
  - `README.md:1-64` — existing structure to extend, not replace

  **Acceptance Criteria**:

  ```
  Scenario: Fresh-clone reviewer reaches green /ready in <5 minutes
    Tool: Bash
    Steps: Follow the Quick Start exactly as written in README, on a machine with Docker + uv installed
    Expected Result: /ready returns 200, /health returns 200, pytest passes
    Failure Indicators: Any step fails with no clear error recovery path
    Evidence: .omo/evidence/task-10-readme-followthrough.txt
  ```

  **Evidence to Capture**:
  - [ ] task-10-readme-followthrough.txt — end-to-end command outputs from fresh clone

  **Commit**: YES (standalone)
  - Message: `docs: Sprint 1 Quick Start + env var documentation`
  - Files: `README.md`, `.env.example`
  - Pre-commit: none

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read this plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": grep codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in `.omo/evidence/`. Compare concrete deliverables against the Concrete Deliverables list.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | DoD Items [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `uv run ruff check app/ scripts/ tests/` + `uv run pytest -q`. Review all Sprint 1 changed/created files for: `# type: ignore`, empty `except:` blocks, `print()` in app/ code (structlog should be used instead), commented-out code, unused imports. Check AI slop: excessive docstrings, over-abstraction, generic names.
  Output: `Ruff [PASS/FAIL] | Pytest [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [x] F3. **Real DoD QA** — `unspecified-high`
  Start from a clean state (stop any running uvicorn, docker compose down -v, docker compose up -d, alembic upgrade head). Execute every DoD item (6 bullet points) + every QA scenario in tasks 1–10. Save all evidence. Verify the README Quick Start works end-to-end.
  Output: `DoD Items [N/6] | QA Scenarios [N/N pass] | README [OK/FAIL] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read the actual files created/modified. Verify: (1) everything in "What to do" is present, (2) nothing in "Must NOT do" was built, (3) no Sprint 2–5 directories were touched. Run `git diff --name-only` (or equivalent) to enumerate changed files. Flag any unaccounted file changes.
  Output: `Tasks [N/10 compliant] | Sprint-2-5 contamination [CLEAN/N files] | VERDICT`

---

## Commit Strategy

| Task | Commit Message | Files |
|------|----------------|-------|
| 1+2 | `chore(infra): Docker Compose + dep additions` | `docker/`, `pyproject.toml`, `uv.lock` |
| 3 | `feat(config): vector, cors, mock-auth settings` | `app/config/settings.py`, `.env.example` |
| 4 | `feat(db): ORM models for all 9 EVA tables` | `app/db/models.py`, `app/db/__init__.py` |
| 5 | `feat(db): Alembic async + schema migrations` | `alembic.ini`, `migrations/` |
| 6 | `feat(retrieval): VectorStore + register_vector` | `app/retrieval/vector_store.py`, `app/schemas/vector.py`, `app/db/session.py` |
| 7 | `feat(api): /ready, structlog, CORS, middleware, auth stub` | `app/main.py`, `app/api/deps.py` |
| 8 | `feat(data): synthetic generator + idempotent seed` | `scripts/`, `data/synthetic/` |
| 9 | `test: pytest suite (testcontainers, vector, seed)` | `tests/` |
| 10 | `docs: Sprint 1 Quick Start + env docs` | `README.md` |

---

## Success Criteria

### Verification Commands
```bash
docker compose -f docker/docker-compose.yml up -d
uv run alembic upgrade head  # Expected: 2 migrations, no errors
uv run python -m scripts.seed_db && uv run python -m scripts.seed_db  # Expected: second run = "already seeded"
uv run uvicorn app.main:app --reload &
curl http://localhost:8000/health  # Expected: {"status":"ok","env":"development"}
curl http://localhost:8000/ready   # Expected: {"status":"ready","db":true,"vector":true}
uv run pytest -q                   # Expected: ≥10 passed, 0 failures
```

### Final Checklist
- [ ] DoD-1: 9 tables exist, Alembic round-trip works
- [ ] DoD-2: 50 scenarios JSONL + 48 markdown docs in data/synthetic/
- [ ] DoD-3: /health + /ready correct; CORS from settings; structlog configured; request-log middleware active
- [ ] DoD-4: Async SQLAlchemy 2.x + asyncpg; psycopg[binary] for Alembic; pool from Settings
- [ ] DoD-5: pgvector extension active; register_vector on both engines; HNSW cosine index; VectorStore exposes upsert/search/delete/count
- [ ] DoD-6: Seed idempotent (second run = no-op)
- [ ] DoD-7: pytest ≥10 tests pass; README Quick Start leads to green /ready in <5 min
