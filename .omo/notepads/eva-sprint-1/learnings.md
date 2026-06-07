# Learnings � EVA Sprint 1

Session started 2026-06-06

## Codebase state at start
- Scaffold: app/main.py with /health, CORS allow_origins=["*"], lifespan stub
- app/config/settings.py: basic Settings class
- app/db/session.py: async engine, Base, get_db_session(), singleton globals
- app/db/__init__.py: re-exports Base + session helpers
- tests/test_health.py: 1 smoke test
- docker/, scripts/, data/synthetic/: empty dirs
- Sprint 2-5 packages: empty __init__.py stubs

## Key decisions
- pgvector/pgvector:0.8.0-pg16 everywhere
- Two Alembic migrations
- register_vector on BOTH sync and async engines
- No factory-boy, no slugify, no Langfuse in Sprint 1
- No embeddings during seed (no Gemini calls)
- /ready pings DB per PRD DoD-3
- UUID PKs with gen_random_uuid()
- Mock-auth stub <=15 LOC, hardcoded return

## 2026-06-07 — Sprint 1 settings fields added

Added 6 new fields to `Settings` (5 from the spec + `cors_origins` and `mock_auth_enabled`):

| Field | Type | Default | Env var |
|---|---|---|---|
| `cors_origins` | `list[str]` | `["http://localhost:3000"]` | `CORS_ORIGINS` |
| `mock_auth_enabled` | `bool` | `True` | `MOCK_AUTH_ENABLED` |
| `embedding_dim` | `int` | `768` | `EMBEDDING_DIM` |
| `vector_index_type` | `Literal["hnsw","ivfflat"]` | `"hnsw"` | `VECTOR_INDEX_TYPE` |
| `hnsw_m` | `int` | `16` | `HNSW_M` |
| `hnsw_ef_construction` | `int` | `64` | `HNSW_EF_CONSTRUCTION` |

- `embedding_dim=768` matches Gemini text-embedding-004 output dimensionality
- `vector_index_type` defaults to `hnsw` (will be read by the VectorStore index builder)
- `cors_origins` is a JSON-list string in the env file, parsed by Pydantic
- `mock_auth_enabled` allows bypassing real auth during development
- `.env.example` updated with two new sections: "CORS & Mock Auth" and "Embeddings & Vector Index"
- Verification: `get_settings().embedding_dim == 768`, env override `EMBEDDING_DIM=512` works

## Dependencies added (2026-06-07)
- `psycopg[binary]>=3.2` — sync Postgres driver for Alembic migrations (runtime)
- `faker>=25` — synthetic data generation for seed scripts (runtime, not dev-only)
- `testcontainers[postgres]>=4.8` — integration test containers (dev extra)
- Verified all three import correctly via `uv run python -c "import psycopg, faker, testcontainers; print('ok')"`

## Docker Compose for local dev DB (2026-06-07)
- Created `docker/docker-compose.yml` with `pgvector/pgvector:0.8.0-pg16`
- Created `docker/postgres/init.sql` with `CREATE EXTENSION IF NOT EXISTS vector;`
- Compose path considerations: paths in `env_file` and `volumes` are relative to the compose file directory (`docker/`), so `env_file: ../.env` points to root `.env`, and `volumes: ./postgres/init.sql` resolves correctly
- Healthcheck: `pg_isready -U eva -d eva` with 5s interval, 3s timeout, 5 retries, 10s start period
- Named volume `eva_pgdata` with `driver: local`
- No top-level `version:` key (Compose V2 format)
- Acceptance command: `docker compose -f docker/docker-compose.yml up -d` (requires Docker Desktop running)
- Created minimal `.env` with `POSTGRES_USER=eva`, `POSTGRES_PASSWORD=eva`, `POSTGRES_DB=eva` to satisfy `env_file`
- Docker Desktop daemon not available in this environment — verify manually with `psql -h localhost -U eva -d eva -c 'SELECT * FROM pg_extension WHERE extname = '\''vector'\'';'`

## 2026-06-07 — ORM models created

Created `app/db/models.py` with 9 tables + TimestampMixin using SQLAlchemy 2.x `Mapped`/`mapped_column()` API:

| Table | PK | FK | Indexes | Notes |
|---|---|---|---|---|
| `customers` | UUID | — | — | email unique |
| `subscriptions` | UUID | customers.id CASCADE | — | — |
| `billing_records` | UUID | customers.id CASCADE, subscriptions.id SET NULL | `ix_billing_records_due_date` | Numeric(12,2) amount |
| `support_tickets` | UUID | customers.id CASCADE | `ix_support_tickets_status` | — |
| `usage_analytics` | UUID | customers.id CASCADE | — | Float metric_value |
| `crm_notes` | UUID | customers.id CASCADE | — | Text content |
| `conversation_sessions` | UUID | customers.id CASCADE | `ix_conversation_sessions_customer_id` | — |
| `conversation_messages` | UUID | conversation_sessions.id CASCADE | — | role CHECK ('user','assistant','system') |
| `knowledge_documents` | UUID | — | — | Vector(768), collection CHECK, metadata JSONB |

Key patterns:
- All PKs: `Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))`
- TimestampMixin with `DateTime(timezone=True)` + `func.now()` for both `created_at`/`updated_at` (latter with `onupdate`)
- `ConversationMessage.metadata_` mapped to `"metadata"` column via `mapped_column("metadata", JSONB, nullable=True)`
- `KnowledgeDocument.embedding` reads `get_settings().embedding_dim` at import time → 768
- No HNSW index in model definition (migration 2)
- `Index()` objects declared at module level, not in `__table_args__`
- All model classes re-exported from `app/db/__init__.py` for Alembic discovery
- Acceptance: `sorted(Base.metadata.tables.keys())` returns all 9 table names

## 2026-06-07 — Alembic async template converted to sync‑only env.py

- `uv run alembic init -t async migrations` bootstraps with `run_async_migrations()` using `AsyncEngine.run_sync()`
- **Replaced** the async template entirely: removed `asyncio`, `async_engine_from_config`; added `create_engine`
- `alembic.ini` has `sqlalchemy.url` commented out — set programmatically from `get_settings().database_url` with `+asyncpg` → `+psycopg` replacement
- `target_metadata = Base.metadata` picks up all models registered on the `DeclarativeBase`
- `pgvector.psycopg.register_vector()` must be called on the **raw psycopg connection**, accessed via `connection.connection.driver_connection` (the pool `_ConnectionFairy` wraps the actual `psycopg.Connection`)
- Sync `Connection` does **not** have `run_sync()` — call `do_run_migrations(connection)` directly
- Native PostgreSQL 18 is also available on this machine (`postgres`/`password`) as fallback when Docker Desktop daemon is not running

## 2026-06-07 — ORM models fixed to match spec columns (22 column changes)

Fixed `app/db/models.py` to add all missing columns from the plan spec. The subagent that created the models had the correct 9-table structure, PKs, FKs, relationships, and Vector(768) — but omitted ~18 columns. Fix summary:

| Model | Change |
|-------|--------|
| Customer | +`plan_tier`, +`is_active` |
| Subscription | `plan`→`plan_name`, +`monthly_amount` |
| BillingRecord | `paid`→`status`, +`currency`, +`description` |
| SupportTicket | `subject`→`title`, +`description`, +`category`, +`assigned_to`, +`resolved_at` |
| UsageAnalytic | `recorded_at`→`period_start`, +`period_end` |
| CRMNote | `created_by`→`author`, +`note_type` |
| ConversationSession | `status`→`session_status`, +`language`, +`summary`, +`tools_used`(JSONB) |
| ConversationMessage | +`tool_calls`(JSONB), +`token_count` |
| KnowledgeDocument | +`source_ref` |

Lesson: Always compare subagent model output against the spec column-by-column. Subagents drop optional-ish columns without flagging it. This is a systematic failure pattern.

## 2026-06-07 — ORM model column additions (22 columns)

Added/migrated 22 columns across all 9 models to match the spec:

| Model | Changes |
|---|---|
| `Customer` | +`plan_tier`, +`is_active` |
| `Subscription` | `plan`→`plan_name`, +`monthly_amount` |
| `BillingRecord` | +`currency`, `paid`→`status`, +`description` |
| `SupportTicket` | `subject`→`title`, +`description`, +`category`, +`assigned_to`, +`resolved_at` |
| `UsageAnalytic` | `recorded_at`→`period_start`, +`period_end` |
| `CRMNote` | `created_by`→`author`, +`note_type` |
| `ConversationSession` | `status`→`session_status`, +`language`, +`summary`, +`tools_used` (JSONB) |
| `ConversationMessage` | +`tool_calls` (JSONB), +`token_count` |
| `KnowledgeDocument` | +`source_ref` |

No table/relationship structure, PKs, FKs, TimestampMixin, or indexes were changed.
All 9 tables still registered, Vector(768) column still passes.

## 2026-06-07 — Alembic migrations created + round-trip verified

Two Alembic migrations successfully autogenerated, hand-tuned, and round-trip tested
on Docker pgvector (PostgreSQL 16, pgvector 0.8.0):

### Migration 1: `98a66ecf9801_init_schema.py`
- **Autogenerated** via `alembic revision --autogenerate -m "init_schema"`
- Added `import pgvector` to fix `NameError` (autogenerator used `pgvector.sqlalchemy.vector.VECTOR` but didn't import the module)
- Added `op.execute("CREATE EXTENSION IF NOT EXISTS vector")` as the very first operation in `upgrade()`
- Captures all 9 tables (`customers`, `subscriptions`, `billing_records`, `support_tickets`, `usage_analytics`, `crm_notes`, `conversation_sessions`, `conversation_messages`, `knowledge_documents`)
- All FK constraints present (CASCADE + SET NULL on `subscription_id`)
- Both check constraints: `ck_conversation_messages_role` and `ck_knowledge_documents_collection`
- All 3 B-tree indexes: `ix_support_tickets_status`, `ix_billing_records_due_date`, `ix_conversation_sessions_customer_id`
- `downgrade()` drops tables in FK-safe reverse order
- No HNSW index (reserved for migration 2)

### Migration 2: `c943d03cdec9_add_hnsw_index.py`
- **Manual** (no autogenerate): `alembic revision -m "add_hnsw_index"`
- Created HNSW index on `knowledge_documents.embedding` with `vector_cosine_ops`, `m=16`, `ef_construction=64`
- **CONCURRENTLY** requires running outside Alembic's transaction:
  - Initial attempts using `raw_conn.autocommit = True` failed with `INTRANS` error (connection already in transaction)
  - Also tried `conn.commit()` before setting autocommit — broke Alembic's internal tracking
  - **Final working approach**: `op.get_context().autocommit_block()` context manager (Alembic 1.18.4 API)
    - This commits the outer Alembic transaction, executes in AUTOCOMMIT, then restores the transaction
    - Works cleanly — no need to touch raw psycopg connections
- `downgrade()` uses `op.execute("DROP INDEX IF EXISTS ...")` inside a normal transaction (safe)

### Round-trip test results (all pass)
1. `uv run alembic upgrade head` ✓ — both migrations apply (exit 0)
2. `uv run alembic current` ✓ — `c943d03cdec9 (head)`
3. `\di ix_knowledge_documents_embedding_hnsw` ✓ — index exists
4. `uv run alembic downgrade -1` ✓ — drops HNSW only (exit 0)
5. `uv run alembic upgrade head` ✓ — re-creates HNSW (exit 0)
6. `uv run alembic downgrade base` ✓ — drops all tables (exit 0)
7. `uv run alembic upgrade head` ✓ — re-applies everything (exit 0)
8. Final `uv run alembic current` ✓ — at head
9. HNSW index exists ✓ — verified via `psql \di` and `pg_indexes`

### Port conflict resolution
- This machine has **both** native PostgreSQL 18.3 (Windows, PID 8684) and Docker pgvector on port 5432
- Python/SQLAlchemy connected to native PostgreSQL 18 instead of Docker pgvector
- Native PG 18 does **not** have the `vector` extension (pgvector is a PostgreSQL 16 extension)
- **Fix**: Changed Docker compose port to `5433:5432` and added `DATABASE_URL=postgresql+asyncpg://eva:eva@localhost:5433/eva` to `.env`
- Lesson: Always verify which PostgreSQL instance migrations are actually hitting

## 2026-06-07 — Synthetic data generator + seed scripts created

Created two scripts in `scripts/`:

### `scripts/generate_synthetic_data.py`
- CLI: `uv run python -m scripts.generate_synthetic_data --seed 42 --out data/synthetic`
- Produces `{out}/eval_scenarios.jsonl` (50 lines, 10 per category: Billing, Subscription, Refund, Product, Account Access)
- Produces `{out}/docs/{collection}/*.md` (48 files, 12 per collection: documentation, policies, knowledge_articles, troubleshooting_guides)
- Each markdown doc ≥ 200 words verified via assertion
- File naming: `{nn}-{kebab-title}.md` using f-string `title.lower().replace(" ", "-")` (no python-slugify)
- Uses `Faker(locale="en_US", seed_instance=<seed>)` — no factory-boy
- Reproducible: same seed = identical output

### `scripts/seed_db.py`
- CLI: `uv run python -m scripts.seed_db [--reset]`
- Idempotent: checks `SELECT COUNT(*) FROM customers` → exits cleanly if > 0 and no `--reset`
- `--reset` truncates 8 tables in FK-safe reverse order with `TRUNCATE ... CASCADE`
- Inserts via `pg_insert(Model).values([...]).on_conflict_do_nothing(index_elements=["id"])`
- Row counts: 20 customers, 30 subscriptions, 90 billing_records, 40 support_tickets, 200 usage_analytics, 30 crm_notes, 25 conversation_sessions, 100 conversation_messages
- Faker(seed=42) for reproducibility; explicit `uuid4()` for all PKs
- Uses `get_session_factory()` from `app.db.session` for async sessions
- NO embedding generation, NO factory-boy, NO knowledge_documents seeding

### Issues encountered
1. **UnicodeEncodeError on Windows**: `≥` character in print statement crashes on cp1252 terminal. Fixed by replacing with `>=`.
2. **Wrong keyword arguments in `_date_between`**: Function uses positional `start`/`end` but was called with `start_date=`/`end_date=`. Fixed by switching to positional args.
3. **Faker date string parsing**: `-1W` (week) not supported by Faker. Replaced with `-7d` (days).
4. **`register_vector` RuntimeWarning**: `app/db/session.py` line 47 fires a `RuntimeWarning` because `register_vector` is a coroutine that's not awaited. This is pre-existing and doesn't block seeding.
5. **Word count discrepancy**: PowerShell's `String.Split(" ")` gives different word counts than Python's `str.split()`. Python's assertion is the source of truth.
6. **`scripts/__init__.py` required**: Using `python -m scripts.*` requires the directory to be a package. Added minimal `__init__.py`.

## 2026-06-07 — app/main.py updated with structlog, CORS from settings, middleware, /ready endpoint

Updated `app/main.py` (55 → 116 lines):

- **Imports**: Added `logging`, `time`, `structlog`, `Depends`, `HTTPException`, `text`, `AsyncSession`, `get_db_session`
- **Lifespan**: Added structlog configuration (JSONRenderer in non-dev, ConsoleRenderer in dev) with startup log message including environment and cors_origins
- **CORS**: Changed `allow_origins=["*"]` to `allow_origins=settings.cors_origins` (defaults to `["http://localhost:3000"]`)
- **Middleware**: Added request-log middleware logging method, path, status_code, duration_ms (no request/response body capture)
- **/ready endpoint**: Pings DB with `SELECT 1`, checks `pg_extension` for `vector`, returns `{"status":"ready","db":True,"vector":True}` or 503 with partial status

Created `app/api/deps.py` (8 LOC):

- `get_current_user()` async stub: checks `settings.mock_auth_enabled`, returns hardcoded `{"customer_id":"mock_001","name":"Mock User","email":"mock@clouddesk.com"}`
- Not wired into any route (Sprint 2 will implement real auth + wire it)
- `app/api/__init__.py` already existed — no changes needed

Verifications:
- `from app.main import app` — ok
- `get_current_user()` returns dict with `customer_id == "mock_001"` — assert passes

## 2026-06-07 — register_vector hook, reset_engine, Pydantic schemas, VectorStore

### app/db/session.py changes
- Added `from sqlalchemy import event` import
- Added `@event.listens_for(engine.sync_engine, "connect")` in `get_engine()` — calls `pgvector.asyncpg.register_vector(dbapi_conn)` so async sessions can pass Python lists as vector type
- Added `reset_engine()` function that sets `_engine` and `_session_factory` to `None` — for test teardown

### app/schemas/vector.py (new)
- `VectorItem`: id (str), collection, title, content, source_ref (default ""), metadata (default {}), embedding (list[float])
- `SearchResult`: id (str), collection, title, content, source_ref, metadata, score (float)

### app/retrieval/vector_store.py (new)
- `VectorStore(session_factory=None)` — defaults to `get_session_factory()`
- All methods use raw `sqlalchemy.text()` — no ORM
- `upsert(items)`: multi-row INSERT with ON CONFLICT DO UPDATE SET; returns rowcount
- `search(collection, query_embedding, top_k=5)`: `<=>` cosine distance, `1 - distance` as score, CAST(:q AS vector)
- `delete(collection, ids)`: DELETE with dynamic IN placeholders
- `count(collection)`: SELECT COUNT(*)
- `truncate(collection)`: DELETE (not DROP TABLE)
- id parameters cast via `CAST(:id AS uuid)`, metadata via `CAST(:metadata AS jsonb)`
- COALESCE used in search to handle NULL source_ref/metadata

## 2026-06-07: Sprint 1 Documentation and Quick Start Completed

- Updated `README.md` to replace the basic Quick Start section with a detailed 10-step clone-to-run sequence.
- Added a Sprint 1 Status checklist to track foundational milestone completeness.
- Documented 6 new configuration variables in `README.md` and `.env.example` to ensure alignment with the Pydantic `Settings` model: `CORS_ORIGINS`, `MOCK_AUTH_ENABLED`, `EMBEDDING_DIM`, `VECTOR_INDEX_TYPE`, `HNSW_M`, and `HNSW_EF_CONSTRUCTION`.
- Kept backend layout and tooling sections intact.
- Verified README.md passes ruff formatting.