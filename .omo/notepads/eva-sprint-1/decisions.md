# Decisions — EVA Sprint 1

| Decision | Rationale |
|---|---|
| pgvector/pgvector:0.8.0-pg16 | plain postgres:16 lacks vector extension |
| Two Alembic migrations | extension race condition; HNSW CONCURRENTLY needs AUTOCOMMIT |
| register_vector on both engines | sync engine needs it for Alembic, async for runtime |
| reset_engine() in session.py | singleton engine globals need test teardown |
| Faker + functions (no factory-boy) | 8 simple functions over 8 factory classes |
| No embeddings in seed | Gemini API dependency breaks offline demos |
| /ready pings DB | PRD DoD-3 requires it |
| UUID PKs | gen_random_uuid() avoids auto-increment collisions |
| Bulk INSERT via execute() | ORM per-row is ~10x slower |
| structlog JSON in prod, Console in dev | standard practice |
| CORS from settings | replace hardcoded allow_origins=["*"] |
| Testcontainers fallback | skip (not fail) when Docker unavailable |
| Mock-auth stub unwired | exists for Sprint 2 import |