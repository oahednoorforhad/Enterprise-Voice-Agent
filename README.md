# EVA — Enterprise Voice Assistant

EVA is a production-grade, multi-source enterprise reasoning system with a real-time voice interface. Customers can speak (in English or Bangla) or type, and EVA retrieves live account data from six independent data sources, reasons across all evidence simultaneously, and responds with a traceable, confidence-calibrated answer—never a hallucination.

**Stack:** Python 3.12 · FastAPI · Gemini 2.5 Native Audio · PostgreSQL + PGVector · React 18 + TanStack Router · Docker

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
- [Evaluation](#evaluation)
- [Observability](#observability)
- [Deployment](#deployment)

---

## Architecture

EVA processes each turn through a five-stage pipeline. The LLM is invoked exactly **three times per turn**—for intent, reasoning, and call summary. Everything else is deterministic.

```mermaid
flowchart TD
    WS["Browser WebSocket\naudio"]
    HTTP["Browser HTTP\ntext chat"]
    API["FastAPI\nvoice_router · chat_router"]
    ORCH["OrchestratorService"]
    IA["① IntentAnalyzer\nLLM → intent label + candidate tools"]
    TS["② ToolSelector\ndeterministic policy → tool plan"]
    TE["③ Tool Execution\nasyncio.gather · parallel · 3 s timeout"]
    ESC["④ EvidenceSufficiencyCheck\ndeterministic → replan if needed"]
    EA["⑤ EvidenceAggregator\nnormalise → EvidencePackage"]
    RP["⑥ ReasoningPipeline\nLLM → evidence-cited conclusion"]
    T1[("Customer\nSQL")]
    T2[("Billing\nSQL")]
    T3[("Tickets\nSQL")]
    T4[("Knowledge\nPGVector")]
    T5[("Analytics\nSQL")]

    WS --> API
    HTTP --> API
    API --> ORCH
    ORCH --> IA --> TS --> TE --> ESC --> EA --> RP
    TE --> T1
    TE --> T2
    TE --> T3
    TE --> T4
    TE --> T5
```

### Voice pipeline (Gemini Native Audio)

```mermaid
sequenceDiagram
    participant B as Browser
    participant S as GeminiLiveSession
    participant G as Gemini 2.5 Flash
    participant DB as PostgreSQL

    B->>S: WebSocket connect
    S->>DB: load 3 prior sessions
    S->>G: open connection + system prompt
    loop Audio streaming
        B->>S: audio frame
        S->>G: relay audio
        G->>S: audio response
        S->>B: relay audio
        G-->>S: tool_call
        S->>DB: execute tool (customer_id injected)
        DB-->>S: tool result
        S->>G: function_response
    end
    B->>S: disconnect
    S->>G: generate_call_summary
    S->>DB: persist summary
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

# 8. Seed database (customer data, knowledge documents)
uv run python -m scripts.seed_db --reset
uv run python -m scripts.seed_knowledge

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

### Auth

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/auth/login/google` | Redirects to Google OAuth consent screen |
| `GET` | `/api/v1/auth/callback/google` | OAuth callback — exchanges code, creates customer, issues JWT |

### Chat

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/chat/` | Single-turn text reasoning |
| `POST` | `/api/v1/chat/stream` | SSE-streamed turn with per-stage events |

**Request body**
```json
{
  "message": "Why was I charged twice this month?",
  "customer_id": "c63d2f89-9aa3-4157-8205-a7d6cfc23207"
}
```

**Response** (`POST /api/v1/chat/`)
```json
{
  "success": true,
  "data": {
    "response": "...",
    "tool_calls_made": ["get_billing_history", "search_policies"],
    "evidence": { "items": [...], "failed_tools": [] },
    "reasoning_trace": { "reasoning_type": "root_cause_analysis", "confidence": 0.92 }
  }
}
```

The stream variant emits `data: { "stage": "intent"|"tools"|"evidence"|"reasoning"|"done", ... }` SSE events.

### Voice

| Method | Path | Description |
|---|---|---|
| `WS` | `/api/v1/voice/stream` | Bidirectional Gemini Live audio stream |
| `GET` | `/api/v1/voice/summary/{session_id}` | Post-call summary |

WebSocket query params: `token=<jwt>` (or any value in mock mode), `customer_id=<uuid>`.

### Tools (LLM-callable endpoints)

All tool endpoints return `{"success": bool, "data": {...}, "error": null}` and always respond with HTTP 200.

| Tool | Method | Path | Description |
|---|---|---|---|
| Customer Profile | `GET` | `/api/v1/tools/customer/profile` | Account details (name, tier, status) |
| Subscription | `GET` | `/api/v1/tools/customer/subscription` | Plan, dates, monthly amount |
| Billing History | `GET` | `/api/v1/tools/billing/history` | 90-day invoices + pending/overdue |
| Billing Refunds | `GET` | `/api/v1/tools/billing/refunds` | Refund records |
| Ticket List | `GET` | `/api/v1/tools/ticket/list` | All open + 30-day closed tickets |
| Ticket Detail | `GET` | `/api/v1/tools/ticket/status` | Single ticket by `ticket_id` |
| Documentation | `POST` | `/api/v1/tools/knowledge/documentation` | Vector search product docs |
| Policies | `POST` | `/api/v1/tools/knowledge/policies` | Vector search policy docs |
| Usage Analytics | `GET` | `/api/v1/tools/analytics/usage` | 90-day usage metrics |

### Demo

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/demo/apply-scenario` | Load a pre-built scenario into a demo account |

Valid scenarios: `billing_dispute`, `technical_bug`, `happy_upgrade`, `churn_risk`, `new_onboarding`.

### Admin

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/admin/set-real-user` | Promote a customer from demo to real user |

Requires `X-Admin-Secret` header matching `ADMIN_SECRET_KEY`.

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the required values. For production, copy `.env.prod.example` to `.env.prod`.

### General

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | `postgresql+asyncpg://eva:eva@localhost:5432/eva` |
| `ENVIRONMENT` | No | `development` | `development` / `staging` / `production` |
| `LOG_LEVEL` | No | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `CORS_ORIGINS` | No | `["http://localhost:3000"]` | JSON array of allowed origins |
| `MOCK_AUTH_ENABLED` | No | `true` | Bypass token validation in dev |

### Google Gemini (Google AI — dev default)

| Variable | Required | Default | Description |
|---|---|---|---|
| `GOOGLE_API_KEY` | Yes | — | Google AI Studio key |
| `GEMINI_MODEL` | No | `gemini-2.0-flash` | Model for intent + reasoning |
| `GEMINI_AUDIO_MODEL` | No | `gemini-2.5-flash-native-audio-dialog` | Voice model (Google AI) |

### Vertex AI (production alternative)

| Variable | Required | Default | Description |
|---|---|---|---|
| `VERTEXAI_ENABLED` | No | `false` | Switch to Vertex AI instead of Google AI |
| `GCP_PROJECT` | No | — | GCP project ID (Vertex AI only) |
| `GCP_LOCATION` | No | `us-central1` | GCP region (Vertex AI only) |
| `GEMINI_AUDIO_MODEL_VERTEX` | No | `gemini-live-2.5-flash-native-audio` | Voice model (Vertex AI) |

### OAuth & JWT

| Variable | Required | Default | Description |
|---|---|---|---|
| `GOOGLE_CLIENT_ID` | For auth | — | Google OAuth 2.0 client ID |
| `GOOGLE_CLIENT_SECRET` | For auth | — | Google OAuth 2.0 client secret |
| `GOOGLE_REDIRECT_URI` | No | `{FRONTEND_URL}/api/v1/auth/callback/google` | OAuth callback URL |
| `FRONTEND_URL` | No | `http://localhost:3000` | Frontend base URL |
| `JWT_SECRET` | For auth | `change_me_in_production` | JWT signing secret |
| `JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm |
| `ADMIN_SECRET_KEY` | For admin | `change_me_admin_secret` | Admin API header secret |

### Embeddings & Vector Index

| Variable | Required | Default | Description |
|---|---|---|---|
| `EMBEDDING_MODEL` | No | `text-embedding-004` | Google embedding model |
| `EMBEDDING_DIM` | No | `768` | Embedding vector dimension |
| `VECTOR_INDEX_TYPE` | No | `hnsw` | `hnsw` or `ivfflat` |
| `HNSW_M` | No | `16` | HNSW links per node |
| `HNSW_EF_CONSTRUCTION` | No | `64` | HNSW candidate list size |

### Database Pool

| Variable | Required | Default | Description |
|---|---|---|---|
| `DB_POOL_SIZE` | No | `10` | SQLAlchemy connection pool size |
| `DB_MAX_OVERFLOW` | No | `5` | Pool overflow limit |

### Reasoning

| Variable | Required | Default | Description |
|---|---|---|---|
| `MAX_TOOL_CALLS_PER_TURN` | No | `6` | Tool call budget per orchestrator turn |
| `RETRIEVAL_TOP_K` | No | `5` | Results per vector search |

### Observability

| Variable | Required | Default | Description |
|---|---|---|---|
| `LANGFUSE_PUBLIC_KEY` | No | — | Langfuse trace public key |
| `LANGFUSE_SECRET_KEY` | No | — | Langfuse trace secret key |
| `LANGFUSE_HOST` | No | `https://cloud.langfuse.com` | Langfuse endpoint |
| `SENTRY_DSN` | No | — | Sentry error monitoring DSN |

---

## Project Structure

```
.
├── app/                           # FastAPI backend
│   ├── api/                       # Routers
│   │   ├── admin_router.py        # POST /api/v1/admin/set-real-user
│   │   ├── auth_router.py         # Google OAuth login + callback
│   │   ├── chat_router.py         # POST /api/v1/chat/ + /stream
│   │   ├── demo_router.py         # POST /api/v1/demo/apply-scenario
│   │   ├── deps.py                # Auth + LLM dependencies
│   │   ├── tools_router.py        # Tool endpoint aggregator
│   │   ├── tools_analytics.py
│   │   ├── tools_billing.py
│   │   ├── tools_customer.py
│   │   ├── tools_knowledge.py
│   │   ├── tools_ticket.py
│   │   └── voice_router.py        # WS /api/v1/voice/stream
│   ├── config/
│   │   └── settings.py            # Pydantic-settings (env-driven)
│   ├── core/
│   │   ├── exceptions.py          # DomainException
│   │   ├── llm_client.py          # Google Gemini SDK wrapper
│   │   └── security.py            # JWT create + verify
│   ├── db/
│   │   ├── models.py              # SQLAlchemy 2.x ORM (9 tables)
│   │   └── session.py             # Async session factory + pooling
│   ├── evaluation/
│   │   └── __init__.py            # 4 scoring functions
│   ├── memory/
│   │   └── db_store.py            # PostgreSQL conversation store
│   ├── observability/
│   │   └── __init__.py            # Langfuse + structlog setup
│   ├── orchestrator/
│   │   ├── service.py             # Main turn loop (intent→tools→reason)
│   │   ├── intent_analyzer.py     # LLM → intent label + tools
│   │   ├── tool_selector.py       # Deterministic policy-based selection
│   │   └── evidence_aggregator.py # Normalise evidence
│   ├── reasoning/
│   │   └── pipeline.py            # Cross-source reasoning + fallback
│   ├── retrieval/
│   │   └── vector_store.py        # PGVector HNSW search
│   ├── schemas/                   # Pydantic models
│   ├── tools/
│   │   ├── analytics/             # Usage metrics queries
│   │   ├── billing/               # Invoice + refund queries
│   │   ├── customer/              # Profile + subscription
│   │   ├── history/               # Session history
│   │   ├── knowledge/             # Vector search + embeddings
│   │   └── ticket/                # Support ticket queries
│   ├── voice/
│   │   ├── session.py             # WebSocket ↔ Gemini Live bridge
│   │   ├── tools.py               # Function declarations
│   │   └── summary.py             # Post-call summary generation
│   └── main.py                    # App factory + middleware
├── frontend/                      # React 18 + Vite + TanStack Router
│   ├── app/
│   │   ├── routes/                # __root, index, app/, scenarios, auth_callback
│   │   ├── components/            # 9 components (VoiceInterface, Sidebar, …)
│   │   ├── hooks/                 # useVoiceSession
│   │   ├── lib/                   # api-client.ts, audio-worklet.ts
│   │   └── styles/                # app.css (Tailwind)
│   ├── public/
│   ├── tests/                     # Vitest + Playwright
│   ├── Dockerfile                 # Multi-stage build
│   ├── nginx.conf                 # SPA fallback for production
│   ├── vite.config.ts
│   └── package.json
├── docker/
│   ├── docker-compose.yml         # Dev: PostgreSQL 16 + PGVector 0.8.0
│   ├── docker-compose.prod.yml    # Prod: all 5 services
│   ├── nginx/                     # nginx.conf, entrypoint.sh, templates/
│   └── postgres/                  # init.sql
├── migrations/                    # Alembic versions (not alembic/)
│   ├── versions/
│   ├── env.py
│   └── script.py.mako
├── tests/                         # ~34 pytest files
├── scripts/
│   ├── deploy.sh                  # GHCR pull + compose restart
│   ├── init-letsencrypt.sh        # One-time SSL bootstrap
│   ├── backup-db.sh
│   ├── generate_synthetic_data.py # Test data generation
│   ├── seed_db.py                 # Customer + billing data seed
│   ├── seed_knowledge.py          # Embed + insert documents
│   ├── seed_single_user.py
│   ├── run_eval.py                # Evaluation harness
│   ├── clear_db.py
│   └── reindex_knowledge.py
├── data/
│   ├── eval/                      # scenarios.yaml + result JSONs
│   ├── scenarios/                 # 5 demo scenario JSONs
│   └── synthetic/                 # Generated fixtures + docs/
├── .github/workflows/
│   └── deploy.yml                 # CI/CD: build + push + SSH deploy
├── docs/
│   └── superpowers/
├── Dockerfile                     # Backend container
├── pyproject.toml
├── .env.example
├── .env.prod.example              # Production env template
└── EVA PRD.md                    # Full product requirements document
```

---

## Tech Stack

### Backend

| Library | Version | Purpose |
|---|---|---|
| Python | 3.12 | Runtime |
| FastAPI | ≥ 0.115 | Web framework + WebSocket |
| Uvicorn | ≥ 0.30 | ASGI server |
| websockets | ≥ 12.0 | WebSocket protocol support |
| SQLAlchemy | ≥ 2.0 | Async ORM |
| asyncpg | ≥ 0.29 | PostgreSQL async driver |
| pgvector | ≥ 0.3.6 | Vector type support |
| Alembic | ≥ 1.13 | Schema migrations |
| google-genai | ≥ 1.0 | Gemini API (chat + audio) |
| Langfuse | ≥ 2.45 | LLM observability |
| Sentry SDK | ≥ 2.0 | Error monitoring |
| Pydantic | ≥ 2.7 | Data validation + settings |
| Pydantic Settings | ≥ 2.4 | Env-driven config |
| structlog | ≥ 24.1 | Structured logging |
| httpx | ≥ 0.27 | Async HTTP client |
| authlib | ≥ 1.3 | OAuth integration |
| PyJWT | ≥ 2.8 | JWT token handling |
| tenacity | ≥ 9.0 | Retry logic |
| Faker | ≥ 25 | Synthetic data generation |

### Frontend

| Library | Version | Purpose |
|---|---|---|
| React | 18.3 | UI framework |
| TanStack Router | 1.120 | Type-safe routing |
| TanStack Query | 5.62 | Server state management |
| Tailwind CSS | 3.4 | Utility-first styling |
| Vite | 5.4 | Build tool |
| Recharts | 2.13 | Data visualization |
| Lucide React | 0.460 | Icon library |
| Sentry React | 10.60 | Frontend error monitoring |
| Vitest | 2.1 | Unit testing |
| Playwright | 1.48 | E2E testing |
| TypeScript | 5.6 | Type safety |

### Infrastructure

| Component | Version | Purpose |
|---|---|---|
| PostgreSQL | 16 | Primary database |
| PGVector | 0.8.0 | Vector similarity search |
| Nginx | Alpine | Reverse proxy + SSL termination |
| Certbot | Latest | Let's Encrypt auto-renewal |
| GitHub Container Registry | — | Docker image registry |
| GitHub Actions | — | CI/CD pipeline |

---

## Database Schema

Nine tables managed by SQLAlchemy ORM with `CASCADE` deletes on all foreign keys.

| Table | Description | Key Columns |
|---|---|---|
| `customers` | Customer accounts | `id`, `name`, `email`, `company`, `plan_tier`, `is_active`, `is_demo`, `google_id`, `active_scenario` |
| `subscriptions` | Plan subscriptions | `customer_id`, `plan_name`, `status`, `monthly_amount`, `start_date`, `end_date` |
| `billing_records` | Invoices & payments | `customer_id`, `subscription_id`, `amount`, `status`, `due_date`, `paid_at`, `description` |
| `support_tickets` | Support issues | `customer_id`, `title`, `category`, `priority`, `status`, `assigned_to` |
| `usage_analytics` | Usage metrics | `customer_id`, `metric_name`, `metric_value`, `period_start`, `period_end` |
| `crm_notes` | Internal CRM notes | `customer_id`, `content`, `note_type`, `author` |
| `conversation_sessions` | Chat + voice sessions | `customer_id`, `session_status`, `language`, `summary` (JSONB), `tools_used` (JSONB), `audio_duration_seconds`, `voice_session_id` |
| `conversation_messages` | Per-turn history | `session_id`, `role`, `content`, `tool_calls` (JSONB) |
| `knowledge_documents` | Vector-indexed docs | `collection`, `title`, `content`, `embedding` (Vector(768)), `source_ref`, `metadata` (JSONB) |

**Indexes:** HNSW vector index on `knowledge_documents.embedding` (created concurrently via migration), plus B-tree indexes on `status`, `due_date`, and `customer_id` columns.

---

## Frontend

The frontend is a **React 18 SPA** built with **Vite** and **TanStack Router** (not Next.js). It uses TanStack Query for server state and Tailwind CSS for styling.

### Routes

| Route | Page | Access | Description |
|---|---|---|---|
| `/` | Landing | Public | Marketing landing page |
| `/auth/callback` | Auth Callback | Public | JWT capture after OAuth redirect |
| `/scenarios` | Scenarios | Auth required | Demo scenario selection (5 pre-built scenarios) |
| `/app/chat` | Chat | Auth required | Single-turn text interface with evidence display |
| `/app/voice` | Voice Call | Auth required | WebSocket audio interface with transcript + call timer |

### Key features

- **Google OAuth login** with JWT stored in `localStorage`
- **Mobile responsive** — bottom tab bar (Chat, Voice, Context, Dark mode, Logout) on mobile; sidebar on desktop
- **Account Context panel** — right-side panel (desktop) or bottom sheet (mobile) showing customer profile, subscription, billing, tickets, analytics
- **Dark mode** — persisted preference, system default detection
- **Backend offline detection** — falls back to mock data when backend is unreachable
- **Streaming chat** — SSE-based per-stage event display
- **Voice call** — WebSocket audio streaming with Gemini Live via `AudioWorklet`

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

**Test files (~34 total):**

| Category | Files |
|---|---|
| Orchestrator | `test_orchestrator.py`, `test_intent_analyzer.py`, `test_tool_selector.py`, `test_evidence_aggregator.py` |
| Reasoning | `test_reasoning_pipeline.py`, `test_reasoning_schemas.py` |
| API Endpoints | `test_chat_api.py`, `test_api.py`, `test_health.py`, `test_api_tools_*.py` |
| Tools | `test_tool_analytics.py`, `test_tool_billing.py`, `test_tool_customer.py`, `test_tool_history.py`, `test_tool_knowledge.py`, `test_tool_ticket.py` |
| Voice | `test_voice_session.py`, `test_voice_router.py`, `test_voice_summary.py`, `test_voice_tools.py`, `test_voice_schema.py`, `test_voice_db_store.py` |
| Auth | `test_auth_deps.py`, `test_auth_security.py` |
| Database | `test_db_models.py`, `test_vector_store.py` |
| Misc | `test_demo_router.py`, `test_llm_client.py`, `test_seed.py` |

### Frontend testing

```bash
cd frontend
npm run test           # Vitest unit tests
npm run test:e2e       # Playwright E2E (headless)
npm run test:e2e:ui    # Playwright with UI
```

---

## Evaluation

EVA includes an automated evaluation harness that scores the system against 50 pre-defined scenarios across 5 categories (billing, subscription, refund_requests, product_problems, account_access).

```bash
# Run all 50 scenarios
uv run python -m scripts.run_eval

# Run one category
uv run python -m scripts.run_eval --category billing

# Dry-run (validate YAML only)
uv run python -m scripts.run_eval --dry-run

# Parallel execution
uv run python -m scripts.run_eval --concurrency 5
```

### Scoring metrics

| Metric | Definition | Threshold |
|---|---|---|
| **Retrieval** | Recall of expected tools called | ≥ 0.50 |
| **Reasoning** | Expected keywords present in answer | ≥ 1.0 |
| **Hallucination** | Forbidden phrases absent from answer | ≥ 1.0 |
| **Quality** | Confidence ≥ min + reasoning type match | ≥ 0.50 |

A scenario **passes** when all 4 metrics meet their thresholds. Results are saved to `data/eval/results_*.json`.

Scenarios are defined in `data/eval/scenarios.yaml` with fields: `id`, `category`, `query`, `expected_tools`, `answer_must_contain`, `answer_must_not_contain`, `min_confidence`, `expected_reasoning_type`. Evaluation scores are computed in `app/evaluation/__init__.py` (pure functions, no DB/API dependencies).

---

## Observability

EVA emits structured logs and optional LLM traces.

**Structured logging** (`structlog`): JSON in production, colorised console in development. The request middleware logs `method`, `path`, `status`, and `duration_ms` on every request. Stdlib fallback configured for subpackages that use `logging.getLogger(__name__)`.

**Langfuse tracing** (optional): Set `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` to enable. The `@observe()` decorator traces intent analysis, tool selection, and reasoning steps. Silently disabled if credentials are absent. Supports both `cloud.langfuse.com` (EU) and `us.cloud.langfuse.com` (US) via `LANGFUSE_HOST`.

**Sentry error monitoring** (optional): Set `SENTRY_DSN` to enable. Captures unhandled exceptions and performance traces at 0.1 sample rate. Frontend Sentry configured with `browserTracingIntegration` and `globalHandlersIntegration`.

---

## Language Support

EVA responds in the language of the customer's message:
- **English** — default
- **Bangla** — detected by Bengali Unicode characters; EVA responds fully in Bangla

Code-switched input (Banglish) is also handled naturally. Hindi and other languages fall back to English.

---

## Deployment

EVA is deployed as a **5-container stack** on a single Ubuntu 24.04 Droplet (2GB/2vCPU) via Docker Compose.

### Production architecture

```
                  Internet
                     |
                  Nginx :443 (SSL)
                  /            \
          Frontend (:80)    Backend (:8000)
          (Nginx SPA)       (FastAPI + Uvicorn)
                                |
                            PostgreSQL :5432
                            (pgvector/pgvector:0.8.0-pg16)
```

| Service | Image | Memory Limit | Health Check |
|---|---|---|---|
| `nginx` | `nginx:alpine` | 128m | — |
| `frontend` | `ghcr.io/{user}/eva-frontend:latest` | 128m | — |
| `backend` | `ghcr.io/{user}/eva-backend:latest` | 512m | `/health` every 10s |
| `postgres` | `pgvector/pgvector:0.8.0-pg16` | 512m | `pg_isready` |
| `certbot` | `certbot/certbot` | 64m | Renews every 12h |

### CI/CD Pipeline (GitHub Actions)

On every push to `main`:

1. Build backend image → push to `ghcr.io/{owner}/eva-backend:latest`
2. Build frontend image (with `VITE_API_URL` build arg) → push to `ghcr.io/{owner}/eva-frontend:latest`
3. SSH into Droplet → `docker compose pull && docker compose up -d`

### Production setup

Prerequisites: Docker, a domain pointing to the Droplet IP, a GitHub Container Registry token.

```bash
# 1. Clone on the Droplet
git clone <repo> /opt/eva
cd /opt/eva

# 2. Configure production environment
cp .env.prod.example .env.prod
# Edit .env.prod: DOMAIN, GITHUB_USERNAME, POSTGRES_PASSWORD, GOOGLE_API_KEY, etc.

# 3. Bootstrap Let's Encrypt SSL
./scripts/init-letsencrypt.sh

# 4. Set up GitHub Actions secrets
#   DROPLET_HOST, DROPLET_SSH_KEY, DOMAIN, VITE_SENTRY_DSN
```

The `init-letsencrypt.sh` script:
1. Creates a dummy self-signed certificate so Nginx starts
2. Starts Nginx + frontend + postgres
3. Requests a real Let's Encrypt certificate via Certbot
4. Reloads Nginx with the real certificate
5. Starts all services

### Manual deploy

```bash
./scripts/deploy.sh     # Pulls latest images and restarts
```
