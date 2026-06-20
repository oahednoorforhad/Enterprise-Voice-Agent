# EVA — Enterprise Voice Assistant

EVA is a production-grade, multi-source enterprise reasoning system with a real-time voice interface. Customers can speak (in English or Bangla) or type, and EVA retrieves live account data from six independent data sources, reasons across all evidence simultaneously, and responds with a traceable, confidence-calibrated answer—never a hallucination.

**Stack:** Python 3.12 · FastAPI · Gemini 2.5 Native Audio · PostgreSQL + PGVector · Next.js (TanStack Router) · Docker

---

## Table of Contents

- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
- [Environment Variables](#environment-variables)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Database Schema](#database-schema)
- [Frontend](#frontend)
- [Testing](#testing)
- [Observability](#observability)

---

## Architecture

EVA processes each turn through a five-stage pipeline. The LLM is invoked exactly **three times per turn**—for intent, reasoning, and call summary. Everything else is deterministic.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Layer                             │
│   Browser WebSocket (audio)    ·    Browser HTTP (text chat)    │
└────────────────────┬────────────────────────┬───────────────────┘
                     │                        │
          WS /voice/stream          POST /api/v1/chat
                     │                        │
┌────────────────────▼────────────────────────▼───────────────────┐
│                     FastAPI Application                          │
│   voice_router (Gemini Live bridge)  ·  chat_router             │
└────────────────────────────────┬────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────┐
│                     OrchestratorService                          │
│                                                                  │
│  1. IntentAnalyzer          LLM → intent label + candidate tools │
│  2. ToolSelector            deterministic policy → tool plan     │
│  3. Tool Execution          asyncio.gather (parallel, 3s timeout)│
│  4. EvidenceSufficiencyCheck deterministic → replan if needed    │
│  5. EvidenceAggregator      normalise → EvidencePackage          │
│  6. ReasoningPipeline       LLM → evidence-cited conclusion      │
└─────────┬──────────┬──────────┬────────────┬────────────┬───────┘
          │          │          │            │            │
     Customer    Billing    Tickets     Knowledge    Analytics
      (SQL)      (SQL)      (SQL)     (PGVector)     (SQL)
```

### Voice pipeline (Gemini Native Audio)

```
Browser ──audio──► GeminiLiveSession ◄──► Gemini 2.5 Flash Native Audio
                        │
                   dispatch_tool()     ← tool calls from model
                        │
                   server-side DB      ← customer_id injected, never exposed
                        │
                 ──► transcript + tools collected on disconnect
                        │
                   generate_call_summary (LLM)
                        │
                   persist to conversation_sessions
```

### Key design decisions

| Decision | Rationale |
|---|---|
| LLM called only 3× per turn | Intent, reasoning, call summary. All selection and routing is deterministic. |
| `customer_id` never sent to LLM | Injected server-side at every tool call. Model only sees results. |
| Parallel tool execution | `asyncio.gather` with independent DB sessions per tool. |
| One replan pass | If evidence is insufficient after the first tool execution, one fallback pass runs with alternate tools. |
| PostgreSQL-backed memory | Sessions and messages stored relationally; 3 prior sessions injected into voice system prompt at zero latency. |

---

## Quick Start

Prerequisites: [uv](https://docs.astral.sh/uv/), Docker, a Google AI API key.

```bash
# 1. Clone
git clone <repo-url>
cd "Enterprise Voice Agent"

# 2. Install dependencies
uv sync

# 3. Copy environment template
cp .env.example .env        # Linux/macOS
copy .env.example .env      # Windows

# 4. Add your Google API key to .env
#    GOOGLE_API_KEY=<your-key-from-aistudio.google.com>

# 5. Start PostgreSQL + PGVector
docker compose -f docker/docker-compose.yml up -d

# 6. Apply migrations (creates schema + HNSW index)
uv run alembic upgrade head

# 7. Generate synthetic test data
uv run python -m scripts.generate_synthetic_data --seed 42

# 8. Seed database
uv run python -m scripts.seed_db --reset

# 9. Start backend
uv run uvicorn app.main:app --reload
```

Verify at:
- `http://localhost:8000/health` → `{"status":"ok"}`
- `http://localhost:8000/ready` → `{"status":"ready","db":true,"vector":true}`

### Frontend

```bash
cd frontend
npm install
npm run dev     # http://localhost:3000
```

---

## API Reference

### Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Returns `{status, env}` |
| `GET` | `/ready` | Checks DB + pgvector connectivity |

### Chat

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/chat/` | Single-turn text interface |

**Request body**
```json
{
  "message": "Why was I charged twice this month?",
  "customer_id": "c63d2f89-9aa3-4157-8205-a7d6cfc23207"
}
```

**Response**
```json
{
  "response": "...",
  "tool_calls": ["get_billing_history", "search_policies"],
  "evidence": { "items": [...], "failed_tools": [] },
  "reasoning_type": "root_cause_analysis",
  "confidence": 0.92
}
```

### Voice

| Method | Path | Description |
|---|---|---|
| `WS` | `/api/v1/voice/stream` | Bidirectional Gemini Live audio stream |
| `GET` | `/api/v1/voice/summary/{session_id}` | Post-call summary |

WebSocket query params: `token=<any>` (mock auth), `customer_id=<uuid>`

### Tools (LLM-callable endpoints)

All tool endpoints return `{"success": bool, "data": {...}, "error": null}` and always respond with HTTP 200.

| Tool | Method | Path | Description |
|---|---|---|---|
| Customer Profile | `GET` | `/api/v1/tools/customer/profile` | Account details (name, tier, status) |
| Subscription | `GET` | `/api/v1/tools/customer/subscription` | Plan, dates, monthly amount |
| Billing History | `GET` | `/api/v1/tools/billing/history` | 90-day invoices + all pending/overdue |
| Ticket List | `GET` | `/api/v1/tools/ticket/list` | All open + 30-day closed tickets |
| Ticket Detail | `GET` | `/api/v1/tools/ticket/status` | Single ticket by `ticket_id` |
| Documentation | `GET` | `/api/v1/tools/knowledge/search-documentation` | Vector search docs |
| Policies | `GET` | `/api/v1/tools/knowledge/search-policies` | Vector search policy docs |
| Usage Analytics | `GET` | `/api/v1/tools/analytics/usage` | 90-day usage metrics |
| Session History | `GET` | `/api/v1/tools/history/sessions` | Last N call summaries |

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the required values.

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | `postgresql+asyncpg://eva:eva@localhost:5432/eva` |
| `GOOGLE_API_KEY` | Yes | — | Google AI Studio key (Gemini access) |
| `ENVIRONMENT` | No | `development` | `development` / `staging` / `production` |
| `LOG_LEVEL` | No | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `CORS_ORIGINS` | No | `["http://localhost:3000"]` | JSON array of allowed origins |
| `MOCK_AUTH_ENABLED` | No | `true` | Bypass token validation in dev |
| `GEMINI_MODEL` | No | `gemini-2.0-flash` | Model for intent + reasoning |
| `GEMINI_AUDIO_MODEL` | No | `gemini-2.5-flash-native-audio-preview-12-2025` | Voice model |
| `VERTEXAI_ENABLED` | No | `false` | Switch to Vertex AI instead of Google AI |
| `GCP_PROJECT` | No | — | GCP project ID (Vertex AI only) |
| `GCP_LOCATION` | No | `us-central1` | GCP region (Vertex AI only) |
| `EMBEDDING_MODEL` | No | `text-embedding-004` | Google embedding model |
| `EMBEDDING_DIM` | No | `768` | Embedding vector dimension |
| `VECTOR_INDEX_TYPE` | No | `hnsw` | `hnsw` or `ivfflat` |
| `HNSW_M` | No | `16` | HNSW links per node |
| `HNSW_EF_CONSTRUCTION` | No | `64` | HNSW candidate list size |
| `MAX_TOOL_CALLS_PER_TURN` | No | `6` | Tool call budget per orchestrator turn |
| `RETRIEVAL_TOP_K` | No | `5` | Results per vector search |
| `DB_POOL_SIZE` | No | `10` | SQLAlchemy connection pool size |
| `DB_MAX_OVERFLOW` | No | `5` | Pool overflow limit |
| `LANGFUSE_PUBLIC_KEY` | No | — | Langfuse observability (optional) |
| `LANGFUSE_SECRET_KEY` | No | — | Langfuse observability (optional) |
| `LANGFUSE_HOST` | No | `https://cloud.langfuse.com` | Langfuse endpoint |

---

## Project Structure

```
.
├── app/
│   ├── api/                  # FastAPI routers
│   │   ├── chat_router.py    # POST /api/v1/chat
│   │   ├── voice_router.py   # WS /api/v1/voice/stream
│   │   ├── tools_router.py   # Tool endpoint aggregator
│   │   ├── tools_analytics.py
│   │   ├── tools_billing.py
│   │   ├── tools_customer.py
│   │   ├── tools_knowledge.py
│   │   └── tools_ticket.py
│   ├── config/
│   │   └── settings.py       # Pydantic settings (env-driven)
│   ├── core/
│   │   ├── llm_client.py     # Google Gemini SDK wrapper
│   │   └── exceptions.py     # Domain exceptions
│   ├── db/
│   │   ├── models.py         # SQLAlchemy 2.x ORM (9 tables)
│   │   └── session.py        # Async session factory + pooling
│   ├── memory/
│   │   └── db_store.py       # PostgreSQL-backed conversation store
│   ├── observability/
│   │   └── __init__.py       # Langfuse + structlog setup
│   ├── orchestrator/
│   │   ├── service.py        # Main turn loop (intent→tools→reason)
│   │   ├── intent_analyzer.py
│   │   ├── tool_selector.py  # Deterministic policy-based selection
│   │   └── evidence_aggregator.py
│   ├── reasoning/
│   │   └── pipeline.py       # Cross-source reasoning + fallback
│   ├── retrieval/
│   │   └── vector_store.py   # PGVector search (HNSW, top-k)
│   ├── schemas/              # Shared Pydantic models
│   ├── tools/
│   │   ├── analytics/        # Usage metrics queries
│   │   ├── billing/          # Invoice queries
│   │   ├── customer/         # Profile + subscription queries
│   │   ├── history/          # Session history retrieval
│   │   ├── knowledge/        # Vector search over docs + policies
│   │   └── ticket/           # Support ticket queries
│   ├── voice/
│   │   ├── session.py        # WebSocket ↔ Gemini Live bridge
│   │   ├── tools.py          # Function declarations for Gemini Live
│   │   └── summary.py        # Post-call summary generation
│   ├── evaluation/
│   │   └── __init__.py       # Scoring: retrieval, reasoning, hallucination, quality
│   └── main.py               # App factory + middleware
├── frontend/                 # Next.js-style (TanStack Router + Vite)
│   ├── app/
│   │   ├── routes/           # Pages: /, /chat, /voice, /dashboard, /analytics, /knowledge
│   │   ├── components/       # VoiceInterface, ChatMessage, Sidebar, MetricCard, …
│   │   ├── hooks/            # Custom React hooks
│   │   └── lib/              # api-client.ts + utilities
│   └── package.json
├── docker/
│   ├── docker-compose.yml    # PostgreSQL 16 + PGVector 0.8.0
│   └── postgres/             # DB init scripts
├── tests/                    # Pytest suite (17 files)
├── scripts/
│   ├── generate_synthetic_data.py
│   └── seed_db.py
├── data/
│   ├── eval/                 # Evaluation scenarios (YAML)
│   └── synthetic/            # Generated test fixtures
├── alembic/                  # Migration scripts
├── pyproject.toml
├── .env.example
└── EVA PRD.md                # Full product requirements document
```

---

## Tech Stack

### Backend

| Library | Version | Purpose |
|---|---|---|
| Python | 3.12 | Runtime |
| FastAPI | ≥ 0.115 | Web framework + WebSocket |
| Uvicorn | ≥ 0.30 | ASGI server |
| SQLAlchemy | ≥ 2.0 | Async ORM |
| asyncpg | ≥ 0.29 | PostgreSQL async driver |
| pgvector | ≥ 0.3.6 | Vector type support |
| Alembic | ≥ 1.13 | Schema migrations |
| google-genai | ≥ 1.0 | Gemini API (chat + audio) |
| Langfuse | ≥ 2.45 | LLM observability |
| Pydantic | ≥ 2.7 | Data validation + settings |
| structlog | ≥ 24.1 | Structured logging |
| tenacity | ≥ 9.0 | Retry logic |

### Frontend

| Library | Version | Purpose |
|---|---|---|
| React | 18.3 | UI framework |
| TanStack Router | 1.120 | File-based routing |
| TanStack Query | 5.62 | Server state management |
| Tailwind CSS | 3.4 | Utility-first styling |
| Vite | 5.4 | Build tool |
| Recharts | 2.13 | Data visualization |
| TypeScript | 5.6 | Type safety |

### Infrastructure

| Component | Version | Purpose |
|---|---|---|
| PostgreSQL | 16 | Primary database |
| PGVector | 0.8.0 | Vector similarity search |
| Docker Compose | — | Local development |

---

## Database Schema

Nine tables managed by SQLAlchemy ORM with `CASCADE` deletes on all foreign keys.

| Table | Description | Key Columns |
|---|---|---|
| `customers` | Customer accounts | `id`, `name`, `email`, `company`, `plan_tier`, `is_active` |
| `subscriptions` | Plan subscriptions | `customer_id`, `plan_name`, `status`, `monthly_amount` |
| `billing_records` | Invoices & payments | `customer_id`, `amount`, `status` (pending/overdue/paid/refunded), `due_date`, `paid_at` |
| `support_tickets` | Support issues | `customer_id`, `title`, `category`, `priority`, `status` (open/in_progress/closed/resolved) |
| `usage_analytics` | Usage metrics | `customer_id`, `metric_name`, `metric_value`, `period_start`, `period_end` |
| `crm_notes` | Internal CRM notes | `customer_id`, `content`, `note_type`, `author` |
| `conversation_sessions` | Chat + voice sessions | `customer_id`, `session_status`, `language`, `summary` (JSONB), `tools_used` (JSONB), `audio_duration_seconds` |
| `conversation_messages` | Per-turn history | `session_id`, `role` (user/assistant/system), `content`, `tool_calls` (JSONB) |
| `knowledge_documents` | Vector-indexed docs | `collection` (documentation/policies/…), `content`, `embedding` (Vector 768-dim) |

**Indexes:** HNSW vector index on `knowledge_documents.embedding` (created concurrently via migration), plus B-tree indexes on `status`, `due_date`, and `customer_id` columns.

---

## Frontend

Six pages accessible from the sidebar:

| Route | Page | Description |
|---|---|---|
| `/` | Dashboard | KPI cards, recent activity |
| `/chat` | Text Chat | Single-turn chat interface with evidence display |
| `/voice` | Voice Call | WebSocket audio interface with transcript + call timer |
| `/dashboard` | Metrics | Analytics overview |
| `/analytics` | Analytics | Detailed usage metrics |
| `/knowledge` | Knowledge | Vector search over documentation and policies |

The `VoiceInterface` component opens a WebSocket to `/api/v1/voice/stream`, streams microphone audio, and plays back Gemini audio responses in real time. The development mock customer ID is `c63d2f89-9aa3-4157-8205-a7d6cfc23207`.

---

## Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=app

# Lint
uv run ruff check .

# Type check
uv run mypy app/
```

Integration tests use `testcontainers[postgres]` to spin up an isolated PostgreSQL + PGVector instance. No external dependencies required.

**Test files (17 total):**
- `test_orchestrator.py` — Full turn loop with mocked tools
- `test_intent_analyzer.py` — Intent classification
- `test_reasoning_pipeline.py` — Evidence-backed reasoning
- `test_chat_api.py` — Chat endpoint integration
- `test_evidence_aggregator.py` — Evidence normalisation
- `test_api_tools_*.py` — Per-tool endpoint tests

**Evaluation scoring** (four metrics, in `app/evaluation/`):

| Metric | Definition |
|---|---|
| Retrieval | Recall of expected tools called |
| Reasoning | Keyword presence in answer |
| Hallucination | Absence of forbidden phrases |
| Quality | Confidence threshold + reasoning type match |

Evaluation scenarios are defined in `data/eval/scenarios.yaml`.

---

## Observability

EVA emits structured logs and optional LLM traces.

**Structured logging** (`structlog`): JSON in production, colorised console in development. The request middleware logs `method`, `path`, `status`, and `duration_ms` on every request.

**Langfuse tracing** (optional): Set `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` to enable. The `@observe()` decorator traces intent analysis, tool selection, and reasoning steps. Silently disabled if credentials are absent.

---

## Language Support

EVA responds in the language of the customer's message:
- **English** — default
- **Bangla** — detected by Bengali Unicode characters; EVA responds fully in Bangla

Code-switched input (Banglish) is also handled naturally. Hindi and other languages fall back to English.
