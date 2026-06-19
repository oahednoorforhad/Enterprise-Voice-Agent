# Sprint 4 Plan: Voice Experience (v2 — Gemini 2.5 Flash Native Audio)

## TL;DR

> **Quick Summary**: Add a voice interaction layer to EVA using the **Gemini 2.5 Flash Native Audio Dialog** model, replacing the deprecated `gemini-2.0-flash-live-001`. A FastAPI WebSocket proxy bridges the browser ↔ Gemini Live API, reusing all 8 existing tool functions. Call summaries are generated and persisted after each session.
>
> **Deliverables**:
> - WebSocket proxy (`/api/v1/voice/stream`) connecting browser ↔ Gemini 2.5 Flash Live
> - Gemini function declarations for all 8 existing tools
> - Call summary generation + persistence to `ConversationSession.summary`
> - Frontend voice page with mic, transcript, tool badges, and summary panel
> - Unit tests for all new backend modules + Playwright component tests for frontend
>
> **Estimated Effort**: Large
> **Parallel Execution**: YES — 5 waves
> **Critical Path**: Task 1 (AudioWorklet schema) → Task 5 (GeminiLiveSession) → Task 9 (router) → Task 12 (frontend hook) → Task 14 (QA)

---

## Context

### Original Request
Evaluate and improve the existing Sprint 4 voice plan to use the **Gemini 2.5 Flash Native Audio Dialog** model instead of the deprecated `gemini-2.0-flash-live-001` (shut down June 1, 2026).

### What Changed from v1 (Claude's Original Plan)
| Change | v1 (Original) | v2 (Improved) |
|--------|--------------|---------------|
| **Model** | `gemini-2.0-flash-live-001` (DEPRECATED) | `gemini-2.5-flash-native-audio-preview-12-2025` (Google AI) / `gemini-live-2.5-flash-native-audio` (Vertex AI) |
| **Audio output rate** | 16kHz (wrong) | 24kHz (correct for native audio) |
| **Browser resampling** | Not addressed | AudioWorklet: browser mic (48kHz) → resample to 24kHz PCM |
| **WebSocket auth** | Raw `customer_id` query param | Token validation via `deps.get_current_user()` |
| **Text from audio** | `response_modalities: ["AUDIO"]` only | + `output_audio_transcription` + `input_audio_transcription` |
| **VAD config** | Not addressed | `realtime_input_config` with explicit sensitivity thresholds |
| **Session length** | Not addressed | `context_window_compression` for sessions >10 min |
| **Router location** | `app/voice/router.py` | `app/api/voice_router.py` (matches existing patterns) |
| **DB column** | None needed | + `voice_session_id` column with Alembic migration |
| **Auth provider** | Google API key only | Support both Vertex AI (prod) + Google AI (dev) via settings |
| **Tool fallback** | Not addressed | Clarifying question to user if all tool calls fail in a turn |
| **Test coverage** | Schemas + summary only | All new files: schemas, tools, session, summary, router, frontend hook, frontend component |
| **QA automation** | Manual browser test | Playwright component tests with mocked WebSocket |

### Key Research Findings
- `gemini-2.0-flash-live-001` is **shut down June 1, 2026** — the plan must use native audio model
- `google-genai>=1.0.0` (v2.8.0 installed) already supports `client.aio.live.connect()` with the new model
- `app/voice/` exists as a placeholder — ready for implementation
- `ConversationSession.summary` and `tools_used` columns exist but are never written to
- 5 tool families (8 functions) exist and are ready for reuse
- FastAPI + WebSocket dependencies already in `pyproject.toml`

### Metis Review
**Critical issues identified and resolved**:
- Audio resampling strategy (browser 48kHz → 24kHz PCM via AudioWorklet) ✅
- WebSocket authentication via `deps.get_current_user()` token validation ✅
- Vertex AI vs Google AI dual auth support via `vertexai_enabled` setting ✅
- `receive()` + `send_realtime_input()` concurrency — verified SDK pattern supports bidirectional streaming ✅
- Tool call fallback — clarifying question on failure ✅
- Router placement → `app/api/voice_router.py` to match existing patterns ✅

---

## Work Objectives

### Core Objective
Implement voice interaction for EVA using **Gemini 2.5 Flash Native Audio Dialog**, with a FastAPI WebSocket proxy that connects a browser-based microphone to the Gemini Live API, reuses all 8 existing tool functions via Gemini function calling, and generates/persists call summaries.

### Concrete Deliverables
- **Backend**: `app/api/voice_router.py`, `app/schemas/voice.py`, `app/voice/tools.py`, `app/voice/session.py`, `app/voice/summary.py`
- **Modified files**: `app/config/settings.py`, `app/db/models.py`, `app/memory/db_store.py`, `app/main.py`, `app/core/llm_client.py`
- **Frontend**: `frontend/app/routes/voice.tsx`, `frontend/app/hooks/useVoiceSession.ts`, `frontend/app/components/VoiceInterface.tsx`, `frontend/app/router.tsx`, `frontend/app/components/Sidebar.tsx`, `frontend/app/lib/api-client.ts`
- **Infrastructure**: Alembic migration for `voice_session_id` column, Playwright config
- **Tests**: 6 test files covering all new backend modules + frontend hook/component tests

### Definition of Done
- [ ] `GET /health` returns 200
- [ ] `GET /ready` returns 200
- [ ] `POST /api/v1/chat` still works (Sprint 3 untouched)
- [ ] `GET /api/v1/voice/summary/{id}` returns `CallSummaryResult` for valid sessions
- [ ] WebSocket `/api/v1/voice/stream` accepts authenticated connections with valid tokens
- [ ] WebSocket `/api/v1/voice/stream` rejects unauthenticated connections with 403
- [ ] `uv run pytest -q --tb=short` — all 22 existing + 6 new tests pass
- [ ] Frontend `/voice` route renders mic, transcript, tool badges, and summary panel
- [ ] Playwright tests pass: `npx playwright test`

### Must Have
- [ ] Bidirectional audio streaming: browser mic → Gemini Live → browser speakers
- [ ] All 8 existing tools callable via voice (function declarations + dispatch)
- [ ] Call summary generated and persisted after each session
- [ ] Transcript display in real-time (user + assistant text via audio transcription)
- [ ] Tool call badges show which tools are being invoked
- [ ] WebSocket authentication prevents unauthorized access

### Must NOT Have (Guardrails)
- [ ] **No changes** to `app/orchestrator/`, `app/reasoning/`, `app/api/chat_router.py`, `app/api/tools_router.py`, `app/tools/*/functions.py`, existing `tests/` files
- [ ] **No ScriptProcessorNode** in frontend (deprecated); use AudioWorklet only
- [ ] **No hardcoded provider** — settings must support both Vertex AI and Google AI
- [ ] **No assumption about mic sample rate** — always resample to 24kHz in AudioWorklet
- [ ] **No live Gemini API dependency in unit tests** — always mock the SDK
- [ ] **No manual QA dependencies** — all scenarios agent-executable (Playwright, curl, pytest)
- [ ] **No full E2E audio capture tests** — not feasible in headless Playwright; mock WebSocket instead
- [ ] **No schema changes beyond `voice_session_id`** — no new tables, no column drops

### Deferred to Sprint 5+ (Explicit Scope OUT)
- Langfuse tracing for WebSocket voice sessions
- Concurrent session guard for same customer
- Mute/unmute during active session
- Speaker selection (audio output device)
- Call duration timer
- Keyboard shortcut for mic toggle
- Session history in voice page
- Settings page for voice (voice selection, speed, language)
- Graceful degradation from voice to text on model failure

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest + 22 existing tests)
- **Automated tests**: TESTS-AFTER (not TDD — unit tests added after implementation for all new files)
- **Frontend QA**: Playwright component tests with mocked WebSocket
- **Framework**: pytest (backend) + Playwright (frontend)

### QA Policy
Every task MUST include agent-executed QA scenarios (see TODO template below).
Evidence saved to `.omo/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Backend API**: Bash (curl) — Send HTTP/WS requests, assert response status + fields
- **Backend modules**: Bash (pytest) — Run unit tests with mocked dependencies
- **Frontend components**: Playwright (playwright skill) — Render, assert DOM, interact
- **Frontend hooks**: Bash (vitest or node REPL) — Import hook, test state machine transitions with mocked WS

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation — schemas, config, infrastructure):
├── Task 1: Voice schemas + AudioWorklet contract
├── Task 2: Settings update (model + provider config)
├── Task 3: DB migration (voice_session_id column)
├── Task 4: Playwright setup + frontend test infrastructure
└── Task 5: Gemini tool declarations for all 8 tools

Wave 2 (Core voice engine — MAX PARALLEL):
├── Task 6: GeminiLiveSession class (app/voice/session.py)
├── Task 7: Call summary generator (app/voice/summary.py)
├── Task 8: update_session_summary() in db_store.py
├── Task 9: LLMClient factory mode (Google AI + Vertex AI)
└── Task 10: AudioWorklet resampler module (browser)

Wave 3 (API layer + frontend hook):
├── Task 11: Voice WebSocket router (app/api/voice_router.py)
├── Task 12: main.py router registration
├── Task 13: useVoiceSession.ts hook (WebSocket + AudioContext)
└── Task 14: VoiceInterface.tsx component

Wave 4 (Integration + testing):
├── Task 15: voice.tsx route page + router.tsx + Sidebar.tsx + api-client.ts
├── Task 16: Backend unit tests (session, summary, schemas, tools, router)
├── Task 17: Frontend unit tests (hook state machine, component rendering)
├── Task 18: Playwright component tests (mocked WebSocket)
└── Task 19: Full integration smoke test script

Wave FINAL (Review — 4 parallel reviewers + user okay):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high + playwright)
└── Task F4: Scope fidelity check (deep)
-> Present results -> Get explicit user okay

Critical Path: Task 1 → Task 6 → Task 11 → Task 13 → Task 15 → Task 19 → F1-F4 → user okay
Parallel Speedup: ~65% faster than sequential
Max Concurrent: 5 (Wave 2)
```

### Dependency Matrix
- **Task 1** (schemas): Blocks 5, 6, 7, 13
- **Task 2** (settings): Blocks 6, 9, 11
- **Task 3** (DB migration): Blocks 8, 11
- **Task 4** (Playwright setup): Blocks 17, 18
- **Task 5** (tool declarations): Blocks 6
- **Task 6** (session.py): Blocks 11
- **Task 7** (summary.py): Blocks 11
- **Task 8** (update_session_summary): Blocks 11
- **Task 9** (LLMClient): Blocks 6
- **Task 10** (AudioWorklet): Blocks 13
- **Task 11** (router): Blocks 12, 19
- **Task 12** (main.py): Blocks 19
- **Task 13** (useVoiceSession): Blocks 14, 15
- **Task 14** (VoiceInterface): Blocks 15
- **Task 15** (voice page): Blocks 19
- **Task 16** (backend tests): Blocks 19
- **Task 17** (frontend unit tests): Blocks 19
- **Task 18** (Playwright tests): Blocks 19
- **Task 19** (integration smoke test): Blocks F1-F4

### Agent Dispatch Summary
- **Wave 1 (5 tasks)**: T1 → `quick`, T2 → `quick`, T3 → `deep`, T4 → `unspecified-high`, T5 → `quick`
- **Wave 2 (5 tasks)**: T6 → `deep`, T7 → `quick`, T8 → `quick`, T9 → `unspecified-high`, T10 → `visual-engineering`
- **Wave 3 (4 tasks)**: T11 → `deep`, T12 → `quick`, T13 → `visual-engineering`, T14 → `visual-engineering`
- **Wave 4 (5 tasks)**: T15 → `visual-engineering`, T16 → `deep`, T17 → `unspecified-high`, T18 → `unspecified-high`, T19 → `deep`
- **FINAL (4 tasks)**: F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [ ] 1. **Voice Schemas + AudioWorklet Contract** — `app/schemas/voice.py`

  **What to do**:
  - Create `VoiceEventType(str, Enum)` with: `AUDIO_CHUNK`, `TRANSCRIPT`, `TOOL_CALL`, `SESSION_STARTED`, `SESSION_ENDED`, `ERROR`, `INTERRUPT`, `END_OF_AUDIO`
  - Create `VoiceEvent(BaseModel)` with: `type`, `data` (base64 str for audio), `text`, `role`, `tool_name`, `status`, `session_id`, `message`
  - Create `CallSummaryResult(BaseModel)` with: `session_id`, `conversation_summary`, `sources_used`, `reasoning_summary`, `recommended_next_actions`
  - Add docstring defining the **AudioWorklet contract**: input = browser mic (48kHz/44.1kHz device rate), must resample to 24kHz/16-bit/mono PCM in AudioWorkletProcessor before base64 encoding. Output = 24kHz/16-bit/mono PCM base64 decoded and queued at native rate.
  - Add docstring: Gemini expects `audio/pcm;rate=24000` input, returns `audio/pcm;rate=24000` output.

  **Must NOT do**:
  - Do not add fields for video, image, or structured output (not supported by native audio model)
  - Do not add `response_modalities: ["TEXT"]` to any config — native audio only supports `["AUDIO"]`

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None needed (pure Pydantic models)
  - **Skills Evaluated but Omitted**: N/A

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (Tasks 2, 3, 4, 5)
  - **Blocks**: 6, 7, 13
  - **Blocked By**: None

  **References**:
  - `app/schemas/reasoning.py` — Existing Pydantic models pattern (BaseModel, Field, ConfigDict)
  - `google.genai.types.LiveConnectConfig` — SDK types for input/output audio transcription
  - `app/voice/__init__.py` — Placeholder to update with proper package docstring

  **Acceptance Criteria**:
  - [ ] `uv run python -c "from app.schemas.voice import VoiceEvent, CallSummaryResult; e=VoiceEvent(type='audio_chunk', data='AAAA'); print(e.model_dump())"` — works without import errors
  - [ ] `uv run python -c "from app.schemas.voice import VoiceEvent, CallSummaryResult; e=VoiceEvent(type='audio_chunk', data='AAAA'); assert e.type == 'audio_chunk'"` — enum validation works
  - [ ] `uv run python -c "from app.schemas.voice import CallSummaryResult; s=CallSummaryResult(session_id='s1', conversation_summary='x', sources_used=[], reasoning_summary='x', recommended_next_actions=[]); assert s.session_id == 's1'"`

  **QA Scenarios**:
  ```
  Scenario: Voice schema round-trip serialization
    Tool: Bash (uv run python)
    Preconditions: app/schemas/voice.py exists with VoiceEvent, CallSummaryResult
    Steps:
      1. Import VoiceEvent, create instance with all fields
      2. Serialize to dict via model_dump()
      3. Re-import from dict via model_validate()
    Expected Result: All fields survive round-trip, enum values validated
    Evidence: .omo/evidence/task-1-schema-roundtrip.txt

  Scenario: CallSummaryResult required fields
    Tool: Bash (uv run python)
    Preconditions: app/schemas/voice.py exists
    Steps:
      1. Try to create CallSummaryResult with missing required fields
      2. Assert validation error raised
    Expected Result: Pydantic validation error with clear message
    Evidence: .omo/evidence/task-1-summary-validation.txt
  ```

  **Commit**: YES
  - Message: `feat(voice): add voice schemas with AudioWorklet contract`
  - Files: `app/schemas/voice.py`, `app/voice/__init__.py`
  - Pre-commit: `uv run python -c "from app.schemas.voice import VoiceEvent, CallSummaryResult"`

- [ ] 2. **Settings Update — Model + Provider Config** — `app/config/settings.py`, `.env.example`

  **What to do**:
  - Update `gemini_audio_model` default to `"gemini-2.5-flash-native-audio-preview-12-2025"` (Google AI dev default)
  - Add `vertexai_enabled: bool = False` — when True, use Vertex AI auth + model IDs
  - Add `gcp_project: str = ""` — GCP project ID for Vertex AI
  - Add `gcp_location: str = "us-central1"` — GCP location for Vertex AI
  - Add `gemini_audio_model_vertex: str = "gemini-live-2.5-flash-native-audio"` — Vertex AI model ID
  - Set `gemini_audio_model` to be dynamically resolved: if `vertexai_enabled`, use `gemini_audio_model_vertex`, else use `gemini_audio_model`
  - Update `.env.example` with new env vars, keeping old `GOOGLE_API_KEY` + adding new ones

  **Must NOT do**:
  - Do not remove `GEMINI_AUDIO_MODEL` from env — keep as alias for Google AI mode
  - Do not change any non-voice settings

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None needed (config/settings changes)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (Tasks 1, 3, 4, 5)
  - **Blocks**: 6, 9, 11
  - **Blocked By**: None

  **References**:
  - `app/config/settings.py:class Settings` — Existing settings pattern (BaseSettings, Field)
  - `.env.example` — Existing env template to update
  - `app/core/llm_client.py` — How existing LLM client initializes (Google AI API key pattern)

  **Acceptance Criteria**:
  - [ ] `uv run python -c "from app.config.settings import settings; print(settings.gemini_audio_model); print(settings.vertexai_enabled)"` — no import errors, correct defaults
  - [ ] `uv run python -c "from app.config.settings import settings; assert not settings.vertexai_enabled"` — default is False
  - [ ] `.env.example` contains `VERTEXAI_ENABLED`, `GCP_PROJECT`, `GCP_LOCATION`

  **QA Scenarios**:
  ```
  Scenario: Settings load with correct defaults
    Tool: Bash (uv run python)
    Preconditions: settings.py updated, no .env override for audio settings
    Steps:
      1. Import settings from app.config.settings
      2. Print gemini_audio_model, vertexai_enabled, gcp_location
      3. Assert vertexai_enabled is False by default
    Expected Result: Settings load with Gemini 2.5 Flash model, Vertex AI disabled
    Evidence: .omo/evidence/task-2-settings-defaults.txt

  Scenario: .env.example contains new voice vars
    Tool: Bash (grep)
    Preconditions: .env.example exists
    Steps:
      1. grep VERTEXAI_ENABLED .env.example
      2. grep GCP_PROJECT .env.example
      3. grep GCP_LOCATION .env.example
    Expected Result: All three variables present in .env.example
    Evidence: .omo/evidence/task-2-env-vars.txt
  ```

  **Commit**: YES
  - Message: `feat(voice): add Vertex AI support + update audio model to 2.5 Flash`
  - Files: `app/config/settings.py`, `.env.example`
  - Pre-commit: `uv run python -c "from app.config.settings import settings"`

- [ ] 3. **DB Migration — Add voice_session_id Column** — `app/db/models.py`, Alembic migration

  **What to do**:
  - Add `voice_session_id: Mapped[str | None] = mapped_column(String(500), nullable=True)` to `ConversationSession`
  - Also add `audio_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)` for analytics
  - Generate Alembic migration: `alembic revision --autogenerate -m "add voice_session_id to conversation_sessions"`
  - Review and edit migration to ensure correct column types
  - Run migration: `alembic upgrade head`
  - Update `app/db/models.py` column definitions

  **Must NOT do**:
  - Do not add new tables — only new nullable columns on existing `conversation_sessions` table
  - Do not modify existing columns or their constraints
  - Do not change any index or foreign key

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: None

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (Tasks 1, 2, 4, 5)
  - **Blocks**: 8, 11
  - **Blocked By**: None

  **References**:
  - `app/db/models.py:ConversationSession` — Existing model with summary, tools_used, session_status columns
  - `migrations/versions/` — Existing Alembic migration files for pattern reference
  - `alembic.ini` — Migration config

  **Acceptance Criteria**:
  - [ ] `uv run alembic upgrade head` — migration applies without errors
  - [ ] `uv run python -c "from app.db.models import ConversationSession; assert hasattr(ConversationSession, 'voice_session_id')"` — column exists
  - [ ] `uv run python -c "from app.db.models import ConversationSession; assert hasattr(ConversationSession, 'audio_duration_seconds')"` — column exists
  - [ ] `uv run alembic downgrade -1` — rollback works cleanly

  **QA Scenarios**:
  ```
  Scenario: Alembic migration applies cleanly
    Tool: Bash (uv run)
    Preconditions: Database running (docker compose up -d), migration not yet applied
    Steps:
      1. Run alembic upgrade head
      2. Check exit code is 0
      3. Verify new columns via alembic current
    Expected Result: Migration applies with exit code 0
    Evidence: .omo/evidence/task-3-migration-upgrade.txt

  Scenario: New columns are nullable
    Tool: Bash (uv run python)
    Preconditions: Migration applied
    Steps:
      1. Inspect column definition via SQLAlchemy inspect
      2. Assert voice_session_id.nullable is True
    Expected Result: Column is nullable (backward compatible)
    Evidence: .omo/evidence/task-3-column-nullable.txt
  ```

  **Commit**: YES
  - Message: `feat(voice): add voice_session_id and audio_duration_seconds columns`
  - Files: `app/db/models.py`, `migrations/versions/*_add_voice_session_id*.py`
  - Pre-commit: `uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head`

- [ ] 4. **Playwright Setup + Frontend Test Infrastructure** — `frontend/playwright.config.ts`, `frontend/tests/`

  **What to do**:
  - Add `@playwright/test` to frontend devDependencies: `npm install -D @playwright/test`
  - Create `frontend/playwright.config.ts` with:
    - Web server: `npx vite --port 3001`
    - Test directory: `tests/`
    - Base URL: `http://localhost:3001`
    - Browser: Chromium only (for speed)
  - Create `frontend/tests/` directory
  - Create `frontend/tests/__mocks__/` directory
  - Create `frontend/tests/__mocks__/websocket.ts` — MockWebSocket class that simulates WS lifecycle:
    - `onopen`, `onmessage`, `onclose`, `onerror` callbacks
    - `send()` records sent messages
    - `close()` triggers cleanup
    - Helper methods: `simulateMessage(data)`, `simulateOpen()`, `simulateClose()`
  - Add test script to `frontend/package.json`: `"test:e2e": "playwright test"`

  **Must NOT do**:
  - Do not install browsers globally — use `npx playwright install chromium`
  - Do not modify any existing frontend files
  - Do not create actual end-to-end tests yet (just infrastructure)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: None

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (Tasks 1, 2, 3, 5)
  - **Blocks**: 17, 18
  - **Blocked By**: None

  **References**:
  - `frontend/package.json` — Existing frontend deps (lucide-react, recharts, etc.)
  - `frontend/vite.config.ts` — Vite config for web server in Playwright
  - `frontend/tsconfig.json` — TypeScript config for test tsconfig

  **Acceptance Criteria**:
  - [ ] `cd frontend && npx playwright install chromium` — installs browser
  - [ ] `cd frontend && npx playwright test --list` — discovers test files (even if empty)
  - [ ] MockWebSocket class can simulate open/message/close lifecycle
  - [ ] `frontend/playwright.config.ts` — web server points to `http://localhost:3001`

  **QA Scenarios**:
  ```
  Scenario: Playwright detects test infrastructure
    Tool: Bash (cd frontend)
    Preconditions: playwright.config.ts exists, chromium installed
    Steps:
      1. Run npx playwright test --list
      2. Check exit code is 0
    Expected Result: Playwright lists test files (can be empty)
    Evidence: .omo/evidence/task-4-playwright-list.txt

  Scenario: MockWebSocket simulates lifecycle
    Tool: Bash (cd frontend && npx tsx)
    Preconditions: tests/__mocks__/websocket.ts exists
    Steps:
      1. Import MockWebSocket, create instance
      2. Call simulateOpen() -> onopen triggered
      3. Call simulateMessage('{"type":"session_started"}') -> onmessage triggered
      4. Call close() -> onclose triggered
    Expected Result: All lifecycle events fire correctly
    Evidence: .omo/evidence/task-4-mock-ws.txt
  ```

  **Commit**: YES
  - Message: `test(voice): add Playwright infrastructure + MockWebSocket`
  - Files: `frontend/playwright.config.ts`, `frontend/tests/__mocks__/websocket.ts`, `frontend/package.json`
  - Pre-commit: `cd frontend && npx playwright test --list`

- [ ] 5. **Gemini Tool Declarations for All 8 Tools** — `app/voice/tools.py`

  **What to do**:
  - Create `GEMINI_TOOL_DECLARATIONS: list[dict]` with one function declaration per tool
  - Map each existing tool to a Gemini-compatible function declaration:
    - `get_customer_profile` — param: `query: string` (search by name/email)
    - `get_subscription_status` — param: `filter: string` (active/expired/all)
    - `get_billing_history` — param: `period: string` (last_month/this_month/quarter/year)
    - `get_support_tickets` — param: `status: string` (open/closed/all)
    - `get_ticket_status` — param: `ticket_id: string`
    - `get_usage_analytics` — param: `period: string` (last_month/this_month/quarter)
    - `search_documentation` — param: `query: string`
    - `search_policies` — param: `query: string`
  - For ALL tools: `customer_id` is NOT exposed to the model — injected server-side from WS connection context
  - Create `dispatch_tool()` function:
    ```python
    async def dispatch_tool(
        tool_name: str,
        args: dict,
        session_factory: async_sessionmaker[AsyncSession],
        customer_id: str,
        user_message: str,
    ) -> dict:
        """Map Gemini function call to real tool function, return serializable dict."""
        # Import tool functions from app/tools/*/functions.py
        # Inject customer_id where needed (customer-scoped tools)
        # Call function, convert Pydantic models to dict via model_dump()
        # Handle DomainException -> return {"error": str(e)}
    ```
  - Ensure all tool returns are JSON-serializable (dicts, lists, strings, numbers, booleans)

  **Must NOT do**:
  - Do NOT modify any file in `app/tools/` — import and call only
  - Do NOT expose `customer_id` as a parameter in any declaration
  - Do NOT add tools that don't exist in the registry (exactly the 8 existing tools)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None needed (declarative data + mapper function)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (Tasks 1, 2, 3, 4)
  - **Blocks**: 6
  - **Blocked By**: None

  **References**:
  - `app/tools/*/functions.py` — All 8 tool functions to create declarations for
  - `app/orchestrator/service.py:DEFAULT_TOOL_REGISTRY` — Shows how tools are registered and called
  - `google.genai.types.Tool`, `google.genai.types.FunctionDeclaration` — SDK types for tool declarations

  **Acceptance Criteria**:
  - [ ] `uv run python -c "from app.voice.tools import GEMINI_TOOL_DECLARATIONS; assert len(GEMINI_TOOL_DECLARATIONS) == 8"` — exactly 8 tools declared
  - [ ] `uv run python -c "from app.voice.tools import GEMINI_TOOL_DECLARATIONS; names=[d['name'] for d in GEMINI_TOOL_DECLARATIONS]; assert all(n in names for n in ['get_billing_history','get_customer_profile','get_subscription_status','get_support_tickets','get_ticket_status','get_usage_analytics','search_documentation','search_policies'])"` — all 8 tools present
  - [ ] `uv run python -c "from app.voice.tools import GEMINI_TOOL_DECLARATIONS; assert all('customer_id' not in json.dumps(d) for d in GEMINI_TOOL_DECLARATIONS)"` — no customer_id exposed
  - [ ] `uv run pytest tests/test_voice_tools.py -q --tb=short` (once test file exists)

  **QA Scenarios**:
  ```
  Scenario: All 8 tools declared with correct names
    Tool: Bash (uv run python)
    Preconditions: app/voice/tools.py exists
    Steps:
      1. Import GEMINI_TOOL_DECLARATIONS
      2. Assert len == 8
      3. Print names to verify
    Expected Result: 8 tools with expected names
    Evidence: .omo/evidence/task-5-tool-declarations.txt

  Scenario: No customer_id in declarations
    Tool: Bash (uv run python)
    Preconditions: app/voice/tools.py exists
    Steps:
      1. Import GEMINI_TOOL_DECLARATIONS
      2. JSON-dump full declarations
      3. Assert 'customer_id' not in string
    Expected Result: customer_id not exposed to Gemini model
    Evidence: .omo/evidence/task-5-no-customer-id.txt
  ```

  **Commit**: YES (groups with 1, 2, 3, 4)
  - Message: `feat(voice): add Gemini tool declarations + dispatch_tool for all 8 tools`
  - Files: `app/voice/tools.py`
  - Pre-commit: `uv run python -c "from app.voice.tools import GEMINI_TOOL_DECLARATIONS, dispatch_tool"`

- [ ] 6. **GeminiLiveSession Class** — `app/voice/session.py`

  **What to do**:
  - Create `GeminiLiveSession` class with constructor accepting:
    - `customer_id: str`, `customer_context: dict`, `conversation_history: str`
    - `session_factory: async_sessionmaker[AsyncSession]`
    - Uses `settings` for model ID + provider config (Google AI vs Vertex AI)
  - Create async method `run(websocket: WebSocket, db_session: AsyncSession) -> tuple[str, list[str]]`:
    - Initialize Google GenAI client (`genai.Client()` for Google AI, `genai.Client(vertexai=True, ...)` for Vertex AI)
    - Build system instruction from customer_context + conversation_history
    - Open Live connection:
      ```python
      async with client.aio.live.connect(
          model=settings.effective_audio_model,  # resolves based on vertexai_enabled
          config=types.LiveConnectConfig(
              response_modalities=["AUDIO"],
              system_instruction=system_prompt,
              tools=[types.Tool(function_declarations=GEMINI_TOOL_DECLARATIONS)],
              speech_config=types.SpeechConfig(
                  voice_config=types.VoiceConfig(
                      prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
                  )
              ),
              input_audio_transcription=types.AudioTranscriptionConfig(
                  language_codes=["en", "bn"]  # English + Bangla support
              ),
              output_audio_transcription=types.AudioTranscriptionConfig(),
              realtime_input_config=types.RealtimeInputConfig(
                  automatic_activity_detection=types.AutomaticActivityDetection(
                      start_of_speech_sensitivity="START_SENSITIVITY_HIGH",
                      end_of_speech_sensitivity="END_SENSITIVITY_HIGH",
                      prefix_padding_ms=20,
                      silence_duration_ms=800,
                  )
              ),
              context_window_compression=types.ContextWindowCompressionConfig(
                  sliding_window=types.SlidingWindow(target_tokens=32000)
              ),
          ),
      ) as live_session:
          # Run two concurrent tasks:
          # Task A: _browser_to_gemini() — read WS chunks → send_realtime_input()
          # Task B: _gemini_to_browser() — iterate receive() → handle tool calls → forward audio/text to WS
          result = await asyncio.gather(task_a, task_b)
    ```
  - `_browser_to_gemini(websocket, live_session)`:
    - Read JSON messages from WebSocket
    - `audio_chunk` type → decode base64 → `session.send_realtime_input(audio=types.Blob(data=bytes, mime_type="audio/pcm;rate=24000"))`
    - `end_of_audio` type → signal turn completion (user stopped speaking)
    - `interrupt` type → stop current playback
    - `close` type → break out of loop
  - `_gemini_to_browser(websocket, live_session)`:
    - Iterate `live_session.receive()` for LiveServerMessage
    - `server_content.model_turn.parts` with `inline_data` → base64 encode → `VoiceEvent(type=AUDIO_CHUNK, data=base64_audio)` to WS
    - `server_content.model_turn.parts` with `function_call` → call `dispatch_tool()` → send `session.send_tool_response(function_responses=...)` → emit TOOL_CALL events to WS
    - `server_content.model_turn.parts` with text → emit TRANSCRIPT events
    - `server_content.input_transcription` → emit TRANSCRIPT with role="user"
    - `server_content.output_transcription` → emit TRANSCRIPT with role="assistant"
    - `tool_call` messages → handle function call from model
    - `turn_complete` → emit turn_complete signal
    - Handle `go_away` signal → initiate graceful session end
  - Error handling: catch exceptions, emit ERROR event to WS, close gracefully
  - Store `voice_session_id` from session handle for reconnection support

  **Must NOT do**:
  - Do NOT set `response_modalities` to anything other than `["AUDIO"]`
  - Do NOT use `ScriptProcessorNode` concepts — AudioWorklet is browser's responsibility
  - Do NOT expose `GOOGLE_API_KEY` or any credentials to the browser
  - Do NOT block on `send_realtime_input()` — audio chunk sending must be non-blocking

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: None

  **Parallelization**:
  - **Can Run In Parallel**: NO (blocked by 1, 2, 5)
  - **Parallel Group**: Wave 2 (with 7, 8, 9, 10)
  - **Blocks**: 11
  - **Blocked By**: 1 (schemas), 2 (settings), 5 (tool declarations), 9 (LLMClient factory)

  **References**:
  - `google.genai` SDK — Live API connect pattern, LiveConnectConfig, LiveServerMessage, Blob
  - `app/orchestrator/service.py:_execute_tools` — Existing tool execution pattern (parallel tool calls)
  - `app/tools/*/functions.py` — The 8 tool functions dispatched by dispatch_tool
  - `app/core/exceptions.py:DomainException` — Expected exception from tools, must be handled
  - Official docs: `https://ai.google.dev/gemini-api/docs/live` — Live API reference

  **Acceptance Criteria**:
  - [ ] `uv run python -c "from app.voice.session import GeminiLiveSession"` — class imports without error
  - [ ] `uv run python -c "from app.voice.session import GeminiLiveSession; assert hasattr(GeminiLiveSession, 'run')"` — run method exists
  - [ ] Unit test: mock `client.aio.live.connect()` to return fake session, verify `run()` calls `send_realtime_input()` and `receive()`
  - [ ] Unit test: `dispatch_tool()` returns correct results for all 8 tools with mocked tool functions
  - [ ] Unit test: error in `dispatch_tool()` returns `{"error": "..."}` dict, not raises

  **QA Scenarios**:
  ```
  Scenario: dispatch_tool handles all 8 tools
    Tool: Bash (uv run pytest)
    Preconditions: tests/test_voice_session.py exists
    Steps:
      1. Run uv run pytest tests/test_voice_session.py::test_dispatch_tool_all_tools -v
      2. Assert all 8 tool dispatches return valid dicts
    Expected Result: All 8 tools dispatch without error
    Evidence: .omo/evidence/task-6-dispatch-all-tools.txt

  Scenario: dispatch_tool handles DomainException gracefully
    Tool: Bash (uv run pytest)
    Preconditions: test mocking a tool that raises DomainException
    Steps:
      1. Run uv run pytest tests/test_voice_session.py::test_dispatch_tool_error -v
      2. Assert result is {"error": "..."} not an exception
    Expected Result: Error is caught and returned as dict
    Evidence: .omo/evidence/task-6-dispatch-error.txt
  ```

  **Commit**: YES (groups with 7, 8, 9)
  - Message: `feat(voice): add GeminiLiveSession with bidirectional audio streaming`
  - Files: `app/voice/session.py`
  - Pre-commit: `uv run python -c "from app.voice.session import GeminiLiveSession"`

- [ ] 7. **Call Summary Generator** — `app/voice/summary.py`

  **What to do**:
  - Create `_SummaryLLMResponse(BaseModel)` with:
    - `conversation_summary: str`
    - `sources_used: list[str]`
    - `reasoning_summary: str`
    - `recommended_next_actions: list[str]`
  - Create `generate_call_summary(llm_client, transcript, tools_called, customer_context) -> CallSummaryResult`:
    - Uses `llm_client.generate_structured()` — same pattern as reasoning pipeline
    - System prompt instructs: "Summarize the conversation, list the actual data sources accessed (from tools_called), describe the reasoning chain, and suggest 2-3 next actions for the customer support agent."
    - Returns `CallSummaryResult` with all fields populated

  **Must NOT do**:
  - Do NOT call any DB operations — pure LLM call, database persistence happens in db_store.py
  - Do NOT use Gemini Live API for summary — use the existing text LLMClient (cheaper, faster)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with 6, 8, 9, 10)
  - **Blocks**: 11
  - **Blocked By**: 1 (schemas)

  **References**:
  - `app/reasoning/pipeline.py` — Existing `generate_structured()` usage pattern
  - `app/core/llm_client.py:LLMClient` — The client class, especially `generate_structured()` method
  - `app/schemas/voice.py:CallSummaryResult` — The target output schema
  - `app/voice/tools.py:GEMINI_TOOL_DECLARATIONS` — Tool names that should appear in sources_used

  **Acceptance Criteria**:
  - [ ] `uv run python -c "from app.voice.summary import generate_call_summary"` — imports without error
  - [ ] Unit test with mocked LLMClient: returns `CallSummaryResult` with all 4 fields
  - [ ] Unit test: fields not empty for realistic transcript input
  - [ ] Unit test: `sources_used` contains tool names from tools_called input

  **QA Scenarios**:
  ```
  Scenario: generate_call_summary returns valid CallSummaryResult
    Tool: Bash (uv run pytest)
    Preconditions: tests/test_voice_summary.py exists with mocked LLMClient
    Steps:
      1. Run uv run pytest tests/test_voice_summary.py::test_summary_happy_path -v
      2. Assert all 4 fields populated, session_id matches input
    Expected Result: Summary generated with correct structure
    Evidence: .omo/evidence/task-7-summary-happy-path.txt

  Scenario: sources_used reflects tools_called
    Tool: Bash (uv run pytest)
    Preconditions: Summary test with known tool list
    Steps:
      1. Call generate with tools_called=["get_billing_history", "get_customer_profile"]
      2. Assert sources_used contains both tool names
    Expected Result: sources_used matches tools_called input
    Evidence: .omo/evidence/task-7-summary-sources.txt
  ```

  **Commit**: YES (groups with 6, 8, 9)
  - Message: `feat(voice): add call summary generator using LLMClient.generate_structured()`
  - Files: `app/voice/summary.py`
  - Pre-commit: `uv run python -c "from app.voice.summary import generate_call_summary"`

- [ ] 8. **update_session_summary() in db_store.py** — `app/memory/db_store.py`

  **What to do**:
  - Add method to `DbConversationStore`:
    ```python
    async def update_session_summary(
        self,
        session: AsyncSession,
        customer_id: str,
        summary: str,
        tools_used: list[str],
        voice_session_id: str | None = None,
        audio_duration_seconds: int | None = None,
    ) -> None:
        """Persist call summary + close the active ConversationSession."""
        conv_session = await self.get_or_create_session(session, customer_id)
        conv_session.summary = summary
        conv_session.tools_used = {"tools": tools_used}
        conv_session.session_status = "closed"
        conv_session.ended_at = func.now()
        if voice_session_id:
            conv_session.voice_session_id = voice_session_id
        if audio_duration_seconds:
            conv_session.audio_duration_seconds = audio_duration_seconds
        await session.flush()
    ```
  - Import `func` from `sqlalchemy` if not already imported at top of file

  **Must NOT do**:
  - Do NOT modify any existing methods in DbConversationStore
  - Do NOT add new columns — only populate existing ones + new voice_session_id
  - Do NOT add a `session.commit()` — caller handles transaction

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with 6, 7, 9, 10)
  - **Blocks**: 11
  - **Blocked By**: 3 (DB migration for voice_session_id)

  **References**:
  - `app/memory/db_store.py:DbConversationStore` — Existing class, methods to mimic
  - `app/db/models.py:ConversationSession` — Model with all columns being populated
  - `app/memory/db_store.py:_close_session()` — Existing private method that sets ended_at

  **Acceptance Criteria**:
  - [ ] `uv run python -c "from app.memory.db_store import DbConversationStore; assert hasattr(DbConversationStore, 'update_session_summary')"` — method exists
  - [ ] Unit test: mock session + async_sessionmaker, call update_session_summary, verify conv_session.summary and .tools_used are set
  - [ ] Unit test: verify session_status changes to "closed"

  **QA Scenarios**:
  ```
  Scenario: update_session_summary sets all fields
    Tool: Bash (uv run pytest)
    Preconditions: tests/test_voice_db_store.py exists
    Steps:
      1. Mock DbConversationStore.get_or_create_session returns mock conv_session
      2. Call update_session_summary with test data
      3. Assert conv_session.summary == test_summary
      4. Assert conv_session.session_status == "closed"
    Expected Result: All fields set correctly
    Evidence: .omo/evidence/task-8-update-summary.txt
  ```

  **Commit**: YES (groups with 6, 7, 9)
  - Message: `feat(voice): add update_session_summary to DbConversationStore`
  - Files: `app/memory/db_store.py`
  - Pre-commit: `uv run python -c "from app.memory.db_store import DbConversationStore"`

- [ ] 9. **LLMClient Factory Mode — Google AI + Vertex AI** — `app/core/llm_client.py`

  **What to do**:
  - Update `LLMClient` to support both Google AI (`api_key`) and Vertex AI (`vertexai=True, project, location`) modes
  - Add `vertexai_enabled` parameter to `LLMClient.__init__()`
  - When `vertexai_enabled=True`:
    - Initialize with `genai.Client(vertexai=True, project=settings.gcp_project, location=settings.gcp_location)`
    - Use Vertex AI model ID: `settings.gemini_audio_model_vertex`
  - When `vertexai_enabled=False`:
    - Existing behavior: `genai.Client(api_key=settings.google_api_key)`
    - Use Google AI model ID: `settings.gemini_audio_model`
  - Add property `effective_audio_model` that returns the correct model ID based on settings
  - Ensure `generate_structured()` works in both modes
  - Update `get_llm_client` dependency in `app/api/deps.py` if needed to pass `vertexai_enabled`

  **Must NOT do**:
  - Do NOT break existing `generate_structured()` usage in reasoning pipeline
  - Do NOT change the interface of any existing method
  - Do NOT require `vertexai_enabled` — default to `False` for backward compatibility

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: None

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with 6, 7, 8, 10)
  - **Blocks**: 6
  - **Blocked By**: 2 (settings)

  **References**:
  - `app/core/llm_client.py` — Existing LLMClient class
  - `app/api/deps.py` — Dependency injection for LLMClient
  - `app/config/settings.py` — Settings with new vertexai_enabled fields
  - Vertex AI docs: `https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/live-api`

  **Acceptance Criteria**:
  - [ ] `uv run python -c "from app.core.llm_client import LLMClient; client = LLMClient(); assert client.vertexai_enabled == False"` — default mode is Google AI
  - [ ] `uv run python -c "from app.core.llm_client import LLMClient; client = LLMClient(); assert client.effective_audio_model == 'gemini-2.5-flash-native-audio-preview-12-2025'"` — correct default model
  - [ ] Existing tests still pass: `uv run pytest tests/test_llm_client.py -q --tb=short`

  **QA Scenarios**:
  ```
  Scenario: LLMClient defaults to Google AI mode
    Tool: Bash (uv run python)
    Preconditions: llm_client.py updated
    Steps:
      1. Import LLMClient
      2. Create instance (no params)
      3. Assert vertexai_enabled is False
    Expected Result: Backward-compatible defaults
    Evidence: .omo/evidence/task-9-llm-defaults.txt

  Scenario: Existing tests still pass
    Tool: Bash (uv run pytest)
    Preconditions: All changes applied
    Steps:
      1. Run uv run pytest tests/test_llm_client.py -q
    Expected Result: All existing LLM client tests pass
    Evidence: .omo/evidence/task-9-existing-tests-pass.txt
  ```

  **Commit**: YES (groups with 6, 7, 8)
  - Message: `feat(voice): add Vertex AI support to LLMClient with dual-provider mode`
  - Files: `app/core/llm_client.py`, `app/api/deps.py` (if changed)
  - Pre-commit: `uv run pytest tests/test_llm_client.py -q --tb=short`

- [ ] 10. **AudioWorklet Resampler Module (Browser)** — `frontend/app/lib/audio-worklet.ts`

  **What to do**:
  - Create `frontend/app/lib/audio-worklet.ts` with:
    - `createResampler(context: AudioContext, targetRate: number)` — Returns AudioWorkletNode
    - `AudioWorkletProcessor` that:
      - Receives input from `getUserMedia()` at device native rate (48kHz/44.1kHz)
      - Uses linear interpolation resampling to convert to target rate (24kHz)
      - Outputs 24kHz, 16-bit, mono PCM
    - Note: AudioWorklet requires a separate JS file (`audio-worklet-processor.js`) loaded via `context.audioWorklet.addModule()`
    - Create `audio-worklet-processor.js` in `frontend/public/` directory
    - The processor:
      - `process(inputs, outputs)`:
        - Read input buffer (device rate)
        - Resample to target rate using linear interpolation
        - Output resampled buffer (mono)
    - Helper `encodePCMToBase64(buffer: Float32Array, sampleRate: number): string`:
      - Convert Float32Array (-1 to 1) to Int16Array (-32768 to 32767)
      - Return base64 of Int16Array bytes
    - Helper `decodePCMFromBase64(base64: string, sampleRate: number): Float32Array`:
      - Decode base64 to Int16Array
      - Convert to Float32Array for AudioBuffer

  **Must NOT do**:
  - Do NOT use `ScriptProcessorNode` (deprecated, high latency)
  - Do NOT assume device sample rate is 48kHz — use `context.sampleRate` to detect
  - Do NOT ship this without testing at both 44.1kHz and 48kHz input rates

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: None

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with 6, 7, 8, 9)
  - **Blocks**: 13
  - **Blocked By**: None

  **References**:
  - `https://developer.mozilla.org/en-US/docs/Web/API/AudioWorklet` — AudioWorklet API reference
  - `frontend/app/lib/` — Existing lib directory for utility modules
  - Gemini Live API docs — Audio format: 24kHz, 16-bit, mono PCM

  **Acceptance Criteria**:
  - [ ] `frontend/app/lib/audio-worklet.ts` exports `createResampler`, `encodePCMToBase64`, `decodePCMFromBase64`
  - [ ] `frontend/public/audio-worklet-processor.js` exists and can be loaded via `audioWorklet.addModule()`
  - [ ] Unit test: encodePCMToBase64 converts 1 second of silence to correct base64 length
  - [ ] Unit test: decodePCMFromBase64(encodePCMToBase64(signal)) ≈ original signal (lossy due to Int16)

  **QA Scenarios**:
  ```
  Scenario: Audio encode/decode round-trip
    Tool: Bash (cd frontend && npx vitest run)
    Preconditions: audio-worklet.ts exists, test file exists
    Steps:
      1. Create Float32Array of known values
      2. Encode to base64
      3. Decode back to Float32Array
      4. Assert values match (within Int16 precision)
    Expected Result: Round-trip preserves signal
    Evidence: .omo/evidence/task-10-audio-roundtrip.txt
  ```

  **Commit**: YES
  - Message: `feat(voice): add AudioWorklet resampler module (browser 48kHz → 24kHz PCM)`
  - Files: `frontend/app/lib/audio-worklet.ts`, `frontend/public/audio-worklet-processor.js`
  - Pre-commit: `cd frontend && npx vitest run tests/audio-worklet.test.ts`

- [ ] 11. **Voice WebSocket Router** — `app/api/voice_router.py`

  **What to do**:
  - Create `voice_router = APIRouter(prefix="/api/v1/voice", tags=["Voice"])`
  - WebSocket endpoint:
    ```python
    @voice_router.websocket("/stream")
    async def voice_stream(
        websocket: WebSocket,
        session: AsyncSession = Depends(get_db_session),
        llm: LLMClient = Depends(get_llm_client),
        current_user: dict = Depends(get_current_user),  # Auth: validates token
    ):
        """Bidirectional audio streaming WebSocket.
        
        Auth: Requires valid authentication via get_current_user (cookie/token).
        Protocol: JSON messages with VoiceEvent schema.
        Audio: 24kHz, 16-bit, mono PCM, base64-encoded.
        """
        await websocket.accept()
        try:
            # 1. Extract customer_id from current_user
            customer_id = current_user["id"]
            # 2. Load customer context from DB
            customer_context = await load_customer_context(session, customer_id)
            # 3. Load conversation history from DbConversationStore
            history = await db_store.format_prompt_context(session, customer_id)
            # 4. Emit session_started event
            session_id = str(uuid.uuid4())
            await websocket.send_json({"type": "session_started", "session_id": session_id})
            # 5. Run GeminiLiveSession
            live_session = GeminiLiveSession(
                customer_id=customer_id,
                customer_context=customer_context,
                conversation_history=history,
                session_factory=async_sessionmaker,
            )
            transcript, tools_called = await live_session.run(websocket, session)
            # 6. Generate and persist call summary
            summary_result = await generate_call_summary(llm, transcript, tools_called, customer_context)
            await db_store.update_session_summary(
                session, customer_id,
                summary=summary_result.model_dump_json(),
                tools_used=tools_called,
                voice_session_id=live_session.live_session_id,
                audio_duration_seconds=live_session.duration_seconds,
            )
            # 7. Emit session_ended
            await websocket.send_json({
                "type": "session_ended",
                "session_id": session_id,
                "summary_ready": True,
            })
        except WebSocketDisconnect:
            logger.info("Voice WebSocket disconnected")
        except Exception as e:
            logger.exception("Voice session error")
            try:
                await websocket.send_json({"type": "error", "message": str(e)})
            except:
                pass
        finally:
            try:
                await websocket.close()
            except:
                pass
    ```
  - GET endpoint:
    ```python
    @voice_router.get("/summary/{session_id}", response_model=CallSummaryResult)
    async def get_call_summary(
        session_id: str,
        session: AsyncSession = Depends(get_db_session),
        current_user: dict = Depends(get_current_user),
    ):
        """Retrieve stored call summary for a session."""
        conv_session = await session.get(ConversationSession, session_id)
        if not conv_session or not conv_session.summary:
            raise HTTPException(status_code=404, detail="Summary not found")
        # Parse stored summary JSON back to CallSummaryResult
        return CallSummaryResult.model_validate_json(conv_session.summary)
    ```
  - Add `load_customer_context()` helper that fetches customer profile data from DB
  - Ensure `deps.get_current_user()` validates the WS connection before audio streaming starts
  - WebSocket auth: Since FastAPI WebSocket doesn't support cookies/headers easily, extract token from query param (`?token=...`) and validate via `get_current_user`-equivalent logic

  **Must NOT do**:
  - Do NOT expose raw `customer_id` without auth validation
  - Do NOT use `app/voice/router.py` — router goes in `app/api/` per existing pattern
  - Do NOT hardcode `session_factory` — use dependency injection

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: None

  **Parallelization**:
  - **Can Run In Parallel**: NO (blocked by 6, 7, 8)
  - **Parallel Group**: Wave 3 (with 12, 13, 14)
  - **Blocks**: 12, 19
  - **Blocked By**: 6 (session.py), 7 (summary.py), 8 (update_session_summary), 2 (settings), 3 (DB migration)

  **References**:
  - `app/api/chat_router.py` — Existing router pattern (Depends, APIRouter, path prefix)
  - `app/api/tools_router.py` — Another router for pattern reference
  - `app/api/deps.py` — get_db_session, get_llm_client, get_current_user dependencies
  - `app/schemas/voice.py:VoiceEvent, CallSummaryResult` — WS message types
  - `app/voice/session.py:GeminiLiveSession` — The session manager
  - `app/voice/summary.py:generate_call_summary` — The summary generator

  **Acceptance Criteria**:
  - [ ] `uv run python -c "from app.api.voice_router import voice_router"` — imports without error
  - [ ] `uv run python -c "from app.api.voice_router import voice_router; assert len(voice_router.routes) == 2"` — 2 routes (WS + GET)
  - [ ] Unit test: WS endpoint returns 403 when no auth token provided
  - [ ] Unit test: GET /summary/{id} returns 404 for unknown session
  - [ ] Unit test: GET /summary/{id} returns CallSummaryResult for valid session

  **QA Scenarios**:
  ```
  Scenario: WS endpoint rejects unauthenticated connections
    Tool: Bash (websocat or python websockets)
    Preconditions: Server running, no token in query
    Steps:
      1. Try connecting to ws://localhost:8000/api/v1/voice/stream
      2. Expect close with 403 status
    Expected Result: Connection rejected with auth error
    Evidence: .omo/evidence/task-11-ws-auth-reject.txt

  Scenario: GET /summary returns 404 for invalid session
    Tool: Bash (curl)
    Preconditions: Server running
    Steps:
      1. curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/voice/summary/nonexistent-id
      2. Assert HTTP 404
    Expected Result: 404 returned for nonexistent summary
    Evidence: .omo/evidence/task-11-summary-404.txt
  ```

  **Commit**: YES
  - Message: `feat(voice): add voice WebSocket router with auth + summary endpoint`
  - Files: `app/api/voice_router.py`
  - Pre-commit: `uv run python -c "from app.api.voice_router import voice_router"`

- [ ] 12. **main.py Router Registration** — `app/main.py`

  **What to do**:
  - Add import: `from app.api.voice_router import voice_router`
  - Add: `app.include_router(voice_router)` after existing routers
  - Add a health check comment: `# Voice router: /api/v1/voice/*`

  **Must NOT do**:
  - Do NOT change any existing router registration
  - Do NOT reorder routers (voice_router goes after chat_router)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None

  **Parallelization**:
  - **Can Run In Parallel**: NO (blocked by 11)
  - **Parallel Group**: Wave 3 (with 13, 14)
  - **Blocks**: 19
  - **Blocked By**: 11 (router)

  **References**:
  - `app/main.py` — Existing imports and router registrations
  - `app/api/voice_router.py` — The router to register

  **Acceptance Criteria**:
  - [ ] `uv run python -c "from app.main import app; routes=[r.path for r in app.routes]; assert '/api/v1/voice/stream' in routes or any('/api/v1/voice' in r.path for r in app.routes)"` — voice routes registered
  - [ ] `uv run python -c "from app.main import app"` — app factory works without import error

  **QA Scenarios**:
  ```
  Scenario: Voice routes registered in app
    Tool: Bash (uv run python)
    Preconditions: main.py updated
    Steps:
      1. Import app from app.main
      2. Print all route paths
      3. Assert /api/v1/voice/summary/ exists
    Expected Result: Voice routes present
    Evidence: .omo/evidence/task-12-routes-registered.txt
  ```

  **Commit**: YES (groups with 11)
  - Message: `feat(voice): register voice router in app factory`
  - Files: `app/main.py`
  - Pre-commit: `uv run python -c "from app.main import app"`

- [ ] 13. **useVoiceSession.ts Hook** — `frontend/app/hooks/useVoiceSession.ts`

  **What to do**:
  - Create React hook `useVoiceSession(customerId: string)` returning:
    - `status: 'idle' | 'connecting' | 'listening' | 'speaking' | 'ended'`
    - `transcript: Array<{role: 'user' | 'assistant', text: string}>`
    - `toolCalls: Array<{toolName: string, status: 'calling' | 'done'}>`
    - `summaryId: string | null`
    - `error: string | null`
    - `start(): Promise<void>` — initialize WS + mic
    - `stop(): void` — close WS + mic
    - `interrupt(): void` — send interrupt message
  - State machine:
    - `idle` → `connecting` on start()
    - `connecting` → `listening` on session_started event
    - `listening` → `speaking` on audio_chunk from server
    - `speaking` → `listening` on turn_complete
    - any → `ended` on session_ended or error
  - WebSocket lifecycle:
    - Connect to `ws://localhost:8000/api/v1/voice/stream?token={authToken}`
    - Get auth token from your auth context (or mock for dev)
    - Reconnect on drop (max 3 retries)
    - Send `{"type": "audio_chunk", "data": "<base64>"}` for mic input
    - Send `{"type": "end_of_audio"}` on silence
    - Send `{"type": "interrupt"}` on interrupt()
  - Audio input:
    - `getUserMedia({ audio: true })` → stream to AudioWorklet
    - AudioWorklet resamples to 24kHz PCM
    - Chunk to base64 → send via WS (every 40ms or so)
    - Use AudioContext.createMediaStreamSource(stream) → AudioWorkletNode
  - Audio output:
    - On `audio_chunk` events: decode base64 → create AudioBuffer (24kHz) → queue for playback
    - Use AudioContext for output (sample rate conversion handled by browser)
    - Buffer management: drop old chunks if queue exceeds 500ms to prevent lag
  - Cleanup:
    - Close WS on unmount
    - Stop mic tracks on unmount
    - Close AudioContext on unmount

  **Must NOT do**:
  - Do NOT use `ScriptProcessorNode` — AudioWorklet only
  - Do NOT assume auth token is available — handle missing token error
  - Do NOT auto-start on mount — user must click mic button
  - Do NOT accumulate infinite transcript — limit to 500 messages

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: None

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with 11, 12, 14)
  - **Blocks**: 14, 15
  - **Blocked By**: 10 (AudioWorklet), 1 (schemas — VoiceEvent types)

  **References**:
  - `frontend/app/hooks/` — Existing hooks pattern
  - `frontend/app/lib/audio-worklet.ts` — AudioWorklet resampler module
  - `frontend/tests/__mocks__/websocket.ts` — MockWebSocket for testing
  - `app/schemas/voice.py` — VoiceEvent schema (WS message types)

  **Acceptance Criteria**:
  - [ ] `useVoiceSession` exports all state fields and action methods
  - [ ] State machine transitions: idle→connecting→listening→speaking→listening→ended
  - [ ] Mocked WS: transcript accumulates correctly for user and assistant messages
  - [ ] Mocked WS: toolCalls array updates correctly
  - [ ] Cleanup: calling stop() closes WS, stops mic, closes AudioContext

  **QA Scenarios**:
  ```
  Scenario: Hook state machine transitions correctly
    Tool: Bash (cd frontend && npx vitest run)
    Preconditions: useVoiceSession.test.ts exists with MockWebSocket
    Steps:
      1. Render hook with mocked WS
      2. Call start() -> assert status is 'connecting'
      3. Mock receive session_started -> assert status is 'listening'
      4. Mock receive audio_chunk -> assert status is 'speaking'
      5. Mock receive turn_complete -> assert status is 'listening'
    Expected Result: State transitions match spec
    Evidence: .omo/evidence/task-13-state-machine.txt

  Scenario: Transcript accumulates correctly
    Tool: Bash (cd frontend && npx vitest run)
    Preconditions: Hook test with mocked WS
    Steps:
      1. Mock 3 transcript events (user, assistant, user)
      2. Assert transcript array has 3 entries with correct roles
    Expected Result: Transcript array matches received messages
    Evidence: .omo/evidence/task-13-transcript.txt
  ```

  **Commit**: YES
  - Message: `feat(voice): add useVoiceSession hook with WebSocket + AudioContext`
  - Files: `frontend/app/hooks/useVoiceSession.ts`
  - Pre-commit: `cd frontend && npx vitest run tests/useVoiceSession.test.ts`

- [ ] 14. **VoiceInterface.tsx Component** — `frontend/app/components/VoiceInterface.tsx`

  **What to do**:
  - Create React component `VoiceInterface` that uses `useVoiceSession` hook
  - States/UI:
    - **Idle**: Large circular mic button with "Click to start" label, pulse border animation
    - **Connecting**: Spinning loader + "Connecting..." text
    - **Listening**: Mic icon pulsing, "Listening..." text, waveform visualization (CSS bars)
    - **Speaking**: Mic icon with sound waves, "EVA is speaking..." text
    - **Ended**: Mic button disabled, "Call ended" text, summary panel appears
  - Transcript display:
    - Scrollable message list (same ChatMessage pattern as chat.tsx)
    - User messages right-aligned (blue/primary), EVA messages left-aligned
    - Auto-scroll to bottom on new messages
  - Tool call badges:
    - When TOOL_CALL event received with status "calling": show small badge with tool name + spinner
    - When status "done": badge turns green with checkmark, auto-dismiss after 2s
  - Summary panel (after session_ended):
    - Show 4 sections from CallSummaryResult:
      1. "Conversation Summary" — conversation_summary text
      2. "Sources Used" — list of sources_used items
      3. "Reasoning Summary" — reasoning_summary text
      4. "Recommended Next Actions" — numbered list
    - Fetch from `/api/v1/voice/summary/{sessionId}` via `getCallSummary()`
  - Error display:
    - When error event received: show red error banner with message
    - Auto-dismiss after 5s

  **Must NOT do**:
  - Do NOT implement settings, mute/unmute, or speaker selection (deferred)
  - Do NOT auto-navigate on call end — let user decide
  - Do NOT use `ScriptProcessorNode` in any audio handling

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: None

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with 11, 12, 13)
  - **Blocks**: 15
  - **Blocked By**: 13 (useVoiceSession hook)

  **References**:
  - `frontend/app/components/ChatMessage.tsx` — Existing message component for transcript styling
  - `frontend/app/routes/chat.tsx` — Existing chat page for layout patterns
  - `lucide-react` — Icons: `Mic`, `MicOff`, `Square`, `Loader2`, `CheckCircle2`, `AlertCircle`
  - `frontend/app/hooks/useVoiceSession.ts` — The hook this component uses

  **Acceptance Criteria**:
  - [ ] Component renders all 5 states correctly (idle/connecting/listening/speaking/ended)
  - [ ] Transcript messages render with correct alignment based on role
  - [ ] Tool call badges appear on "calling" and show checkmark on "done"
  - [ ] Summary panel renders 4 sections after session_ended
  - [ ] Error banner appears on ERROR event, auto-dismisses after 5s

  **QA Scenarios**:
  ```
  Scenario: Mic button renders in idle state
    Tool: Playwright (npx playwright test)
    Preconditions: playwright.config.ts, component test
    Steps:
      1. Mount VoiceInterface with mocked useVoiceSession (idle state)
      2. Assert mic button is visible
      3. Assert "Click to start" text is present
    Expected Result: Idle state renders correctly
    Evidence: .omo/evidence/task-14-idle-state.png

  Scenario: Tool call badge appears and resolves
    Tool: Playwright (npx playwright test)
    Preconditions: Component rendered, hook mocked to emit tool_call
    Steps:
      1. Mock tool_call "calling" event
      2. Assert badge with tool name + spinner appears
      3. Mock tool_call "done" event
      4. Assert badge changes to checkmark
    Expected Result: Tool badges animate correctly
    Evidence: .omo/evidence/task-14-tool-badges.png
  ```

  **Commit**: YES
  - Message: `feat(voice): add VoiceInterface component with mic, transcript, and summary panel`
  - Files: `frontend/app/components/VoiceInterface.tsx`
  - Pre-commit: `cd frontend && npx playwright test tests/VoiceInterface.test.tsx`

- [ ] 15. **Voice Page + Router + Sidebar + API Client** — Integration wiring

  **What to do**:
  - Create `frontend/app/routes/voice.tsx`:
    - TanStack Router page component
    - Layout: centered card, title "Voice Assistant", `VoiceInterface` component
    - "Switch to Chat" link at bottom (navigates to /chat)
  - Update `frontend/app/router.tsx`:
    - Add route: `{ path: '/voice', component: VoicePage }` (or TanStack Router's `createRoute`)
  - Update `frontend/app/components/Sidebar.tsx`:
    - Add "Voice" nav item with `Mic` icon from lucide-react
    - Place between "Chat" and "Dashboard" items
    - Active state highlighting on `/voice` route
  - Update `frontend/app/lib/api-client.ts`:
    - Add `async getCallSummary(sessionId: string): Promise<CallSummaryResult>`
    - Endpoint: `GET /api/v1/voice/summary/{sessionId}`
    - Return typed response matching CallSummaryResult interface

  **Must NOT do**:
  - Do NOT add navigation guard when leaving voice page (deferred UX)
  - Do NOT modify any existing route's component or behavior
  - Do NOT remove existing sidebar items

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: None

  **Parallelization**:
  - **Can Run In Parallel**: NO (blocked by 13, 14)
  - **Parallel Group**: Wave 4 (with 16, 17, 18, 19)
  - **Blocks**: 19
  - **Blocked By**: 13 (useVoiceSession), 14 (VoiceInterface)

  **References**:
  - `frontend/app/router.tsx` — Existing route definitions (pattern: createRoute, rootRoute)
  - `frontend/app/components/Sidebar.tsx` — Existing sidebar with Chat/Dashboard items
  - `frontend/app/lib/api-client.ts` — Existing API client functions
  - `frontend/app/routes/chat.tsx` — Existing page layout pattern

  **Acceptance Criteria**:
  - [ ] `frontend/app/routes/voice.tsx` renders without import errors
  - [ ] Navigation to `/voice` shows VoiceInterface
  - [ ] Sidebar shows "Voice" nav item with Mic icon, navigates to /voice
  - [ ] `getCallSummary(sessionId)` makes correct API request

  **QA Scenarios**:
  ```
  Scenario: Voice page renders in browser
    Tool: Playwright
    Preconditions: Server running, VoiceInterface mocked
    Steps:
      1. Navigate to http://localhost:3001/voice
      2. Assert page title contains "Voice Assistant"
      3. Assert mic button is visible
    Expected Result: Voice page renders with components
    Evidence: .omo/evidence/task-15-voice-page.png

  Scenario: Sidebar Voice link navigates to /voice
    Tool: Playwright
    Preconditions: Server running
    Steps:
      1. Navigate to http://localhost:3001/chat
      2. Click "Voice" in sidebar
      3. Assert URL is http://localhost:3001/voice
    Expected Result: Navigation works correctly
    Evidence: .omo/evidence/task-15-sidebar-nav.png
  ```

  **Commit**: YES
  - Message: `feat(voice): add voice page, sidebar nav, and API client`
  - Files: `frontend/app/routes/voice.tsx`, `frontend/app/router.tsx`, `frontend/app/components/Sidebar.tsx`, `frontend/app/lib/api-client.ts`
  - Pre-commit: `cd frontend && npx playwright test tests/voice-page.test.tsx`

- [ ] 16. **Backend Unit Tests (All New Modules)** — 6 test files

  **What to do**:
  - Create `tests/test_voice_schema.py`:
    - `test_voice_event_roundtrip()` — VoiceEvent serialization/deserialization
    - `test_voice_event_invalid_type()` — Enum validation error
    - `test_call_summary_result_fields()` — All fields required, correct types
    - `test_audio_worklet_contract_docstring()` — Contract docstring mentions 24kHz resampling
  - Create `tests/test_voice_tools.py`:
    - `test_all_8_tools_declared()` — GEMINI_TOOL_DECLARATIONS has 8 entries
    - `test_customer_id_not_exposed()` — customer_id not in any declaration
    - `test_dispatch_tool_name_validation()` — Invalid tool name raises ValueError
  - Create `tests/test_voice_session.py`:
    - `test_dispatch_tool_all_8()` — All 8 tools dispatch correctly with mocked functions
    - `test_dispatch_tool_domain_exception()` — DomainException returns error dict
    - `test_dispatch_tool_customer_injection()` — customer_id injected for customer-scoped tools
    - `test_dispatch_tool_non_customer_tools()` — Knowledge tools don't get customer_id
    - `test_gemini_live_session_import()` — Class imports and has run method
  - Create `tests/test_voice_summary.py`:
    - `test_generate_call_summary()` — Mock LLMClient, assert CallSummaryResult structure
    - `test_summary_empty_transcript()` — Handle empty transcript gracefully
  - Create `tests/test_voice_router.py`:
    - `test_router_routes_registered()` — 2 routes on voice_router (WS + GET)
    - `test_get_summary_404()` — GET /summary/{id} with nonexistent id
    - `test_get_summary_not_authenticated()` — 401 without auth token
  - Create `tests/test_voice_db_store.py`:
    - `test_update_session_summary()` — Fields set correctly
    - `test_update_session_closes_session()` — session_status changes to "closed"
    - `test_update_session_with_voice_id()` — voice_session_id stored
  - All tests use pytest + mocking — NO live Gemini API, NO real database
  - Use `pytest-asyncio` for async tests (already configured in pyproject.toml)

  **Must NOT do**:
  - Do NOT call real Gemini API in any test
  - Do NOT require running database server (unit tests only)
  - Do NOT modify any existing test files

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: None

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with 15, 17, 18, 19)
  - **Blocks**: 19
  - **Blocked By**: 1, 5, 6, 7, 8, 11 (all backend modules)

  **References**:
  - `tests/test_tool_billing.py` — Existing test for mocking tool functions
  - `tests/test_llm_client.py` — Existing test for mocking LLMClient
  - `conftest.py` — Existing fixtures
  - `app/voice/session.py`, `app/voice/summary.py`, `app/voice/tools.py`, `app/api/voice_router.py`, `app/schemas/voice.py`, `app/memory/db_store.py` — All modules under test

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/test_voice_schema.py tests/test_voice_tools.py tests/test_voice_session.py tests/test_voice_summary.py tests/test_voice_router.py tests/test_voice_db_store.py -q --tb=short` — all pass
  - [ ] Test count ≥ 20 (6 files × ~3-5 tests each)
  - [ ] All tests use mocked dependencies
  - [ ] `uv run pytest -q --tb=short` — all 22 existing tests still pass

  **QA Scenarios**:
  ```
  Scenario: All voice unit tests pass
    Tool: Bash (uv run pytest)
    Preconditions: All voice test files exist
    Steps:
      1. Run uv run pytest tests/test_voice_*.py -v
      2. Assert all tests pass
    Expected Result: All voice tests green
    Evidence: .omo/evidence/task-16-all-voice-tests.txt

  Scenario: Existing tests still pass
    Tool: Bash (uv run pytest)
    Preconditions: No changes to existing code
    Steps:
      1. Run uv run pytest -q --tb=short
      2. Assert 0 failures
    Expected Result: All existing tests pass
    Evidence: .omo/evidence/task-16-existing-tests.txt
  ```

  **Commit**: YES
  - Message: `test(voice): add unit tests for all voice backend modules`
  - Files: `tests/test_voice_schema.py`, `tests/test_voice_tools.py`, `tests/test_voice_session.py`, `tests/test_voice_summary.py`, `tests/test_voice_router.py`, `tests/test_voice_db_store.py`
  - Pre-commit: `uv run pytest tests/test_voice_*.py -q --tb=short`

- [ ] 17. **Frontend Unit Tests (Hook + Audio Module)** — `frontend/tests/useVoiceSession.test.ts`, `frontend/tests/audio-worklet.test.ts`

  **What to do**:
  - Create `frontend/tests/useVoiceSession.test.ts`:
    - `test_initial_state()` — status is 'idle', transcript empty, no error
    - `test_start_connects_websocket()` — start() creates WebSocket
    - `test_state_transitions()` — All state transitions work via mocked WS messages
    - `test_transcript_accumulates()` — Transcript array grows with each message
    - `test_tool_calls_update()` — Tool call badges array updates correctly
    - `test_interrupt_sends_message()` — interrupt() sends correct WS message
    - `test_stop_cleans_up()` — stop() closes WS + mic + AudioContext
    - `test_ws_reconnect()` — Reconnects on drop (up to 3 retries)
    - `test_transcript_limit_500()` — Truncates to 500 messages
    - All using MockWebSocket from `tests/__mocks__/websocket.ts`
  - Create `frontend/tests/audio-worklet.test.ts`:
    - `test_encode_pcm_base64()` — Encode Float32Array to base64, verify format
    - `test_decode_pcm_base64()` — Decode base64 back to Float32Array
    - `test_roundtrip_preserves_signal()` — encode then decode ≈ original
    - `test_silence_encoding()` — Encode 1 second of silence, verify length
  - Install `vitest` if not already: `npm install -D vitest`
  - Add test script: `"test": "vitest run"` to frontend/package.json

  **Must NOT do**:
  - Do NOT test audio playback or microphone — these require browser APIs that vitest can't mock
  - Do NOT import React components in hook tests — test hook in isolation via `renderHook` from `@testing-library/react`

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: None

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with 15, 16, 18, 19)
  - **Blocks**: 19
  - **Blocked By**: 4 (Playwright setup), 13 (useVoiceSession), 10 (audio-worklet)

  **References**:
  - `frontend/tests/__mocks__/websocket.ts` — MockWebSocket class
  - `frontend/app/hooks/useVoiceSession.ts` — Hook under test
  - `frontend/app/lib/audio-worklet.ts` — Audio module under test
  - `@testing-library/react` — renderHook utility for testing hooks

  **Acceptance Criteria**:
  - [ ] `cd frontend && npx vitest run` — all frontend unit tests pass
  - [ ] ≥ 12 frontend unit tests total
  - [ ] MockWebSocket is used for all hook tests
  - [ ] Audio round-trip test passes

  **QA Scenarios**:
  ```
  Scenario: All frontend unit tests pass
    Tool: Bash (cd frontend)
    Preconditions: Test files exist, vitest installed
    Steps:
      1. Run npx vitest run
      2. Assert all tests pass
    Expected Result: All frontend unit tests green
    Evidence: .omo/evidence/task-17-frontend-tests.txt
  ```

  **Commit**: YES (groups with 18)
  - Message: `test(voice): add frontend unit tests for hook and audio module`
  - Files: `frontend/tests/useVoiceSession.test.ts`, `frontend/tests/audio-worklet.test.ts`
  - Pre-commit: `cd frontend && npx vitest run`

- [ ] 18. **Playwright Component Tests (Mocked WebSocket)** — `frontend/tests/VoiceInterface.test.tsx`, `frontend/tests/VoicePage.test.tsx`

  **What to do**:
  - Create `frontend/tests/VoiceInterface.test.tsx`:
    - `test_idle_state()` — Mic button visible, "Click to start" text
    - `test_connecting_state()` — Spinner + "Connecting..." text
    - `test_listening_state()` — Pulsing mic + "Listening..." text
    - `test_speaking_state()` — Sound waves + "EVA is speaking..." text
    - `test_transcript_display()` — Multiple transcript messages render correctly
    - `test_tool_call_badge()` — Badge appears for "calling", checkmark for "done"
    - `test_error_banner()` — Error event shows red banner, auto-dismisses
    - Use `page.route()` to mock WebSocket traffic: intercept WS connections
    - For state testing, use page.evaluate() to trigger hook state changes
  - Create `frontend/tests/VoicePage.test.tsx`:
    - `test_page_renders()` — Page title "Voice Assistant" visible
    - `test_switch_to_chat_link()` — Link navigates to /chat
  - Use `@playwright/test` for test runner
  - Mock WS by using `page.route('ws://localhost:8000/api/v1/voice/stream*', route => ...)` or injecting MockWebSocket via `page.addInitScript`

  **Must NOT do**:
  - Do NOT test actual audio capture/playback (not feasible in headless Playwright)
  - Do NOT require real WebSocket server — mock all WS traffic
  - Do NOT run against production endpoints

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: None

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with 15, 16, 17, 19)
  - **Blocks**: 19
  - **Blocked By**: 4 (Playwright setup), 14 (VoiceInterface), 15 (voice page)

  **References**:
  - `frontend/tests/__mocks__/websocket.ts` — MockWebSocket
  - `frontend/playwright.config.ts` — Playwright config
  - `frontend/app/components/VoiceInterface.tsx` — Component under test
  - `frontend/app/routes/voice.tsx` — Page under test

  **Acceptance Criteria**:
  - [ ] `cd frontend && npx playwright test` — all Playwright tests pass
  - [ ] ≥ 8 Playwright test cases total
  - [ ] All WS communication is mocked — no real backend connection needed
  - [ ] Screenshots captured for visual state verification

  **QA Scenarios**:
  ```
  Scenario: Playwright tests pass with mocked WS
    Tool: Bash (cd frontend)
    Preconditions: Frontend dev server running
    Steps:
      1. Run npx playwright test
      2. Assert all tests pass
    Expected Result: Playwright tests green
    Evidence: .omo/evidence/task-18-playwright-results.txt
  ```

  **Commit**: YES (groups with 17)
  - Message: `test(voice): add Playwright component tests with mocked WebSocket`
  - Files: `frontend/tests/VoiceInterface.test.tsx`, `frontend/tests/VoicePage.test.tsx`
  - Pre-commit: `cd frontend && npx playwright test`

- [ ] 19. **Full Integration Smoke Test Script** — `.omo/integration-smoke.sh`

  **What to do**:
  - Create `.omo/integration-smoke.sh` (or `.ps1` for Windows) that:
    1. Starts backend: `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 &`
    2. Waits for `/health` to return 200
    3. Verifies `GET /health` → status "ok"
    4. Verifies `GET /ready` → status "ready"
    5. Verifies `POST /api/v1/chat` with test message → response has 'response' field
    6. Verifies `GET /api/v1/voice/summary/nonexistent` → 404
    7. Verifies all voice unit tests pass: `uv run pytest tests/test_voice_*.py -q --tb=short`
    8. Verifies all existing tests pass: `uv run pytest -q --tb=short`
    9. Verifies frontend builds: `cd frontend && npx vite build`
    10. Kills background processes
  - This script is the **gate** for the Final Verification Wave — all checks must pass
  - Store evidence files in `.omo/evidence/`

  **Must NOT do**:
  - Do NOT include WebSocket audio streaming in smoke test (requires real mic + Gemini API)
  - Do NOT run against production — local development only
  - Do NOT run Playwright tests in this script (they need dev server separately)

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: None

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on everything)
  - **Parallel Group**: Wave 4 (with 15, 16, 17, 18)
  - **Blocks**: F1-F4
  - **Blocked By**: 12 (main.py), 15 (voice page), 16 (backend tests), 17 (frontend unit tests), 18 (Playwright tests)

  **References**:
  - `.omo/plans/eva-sprint-4-v2.md` — This plan's acceptance criteria
  - `pyproject.toml` — Test configuration
  - `frontend/vite.config.ts` — Build configuration

  **Acceptance Criteria**:
  - [ ] Script completes all 10 checks with zero failures
  - [ ] All evidence files saved to `.omo/evidence/`
  - [ ] Exit code 0 on success, non-zero on failure

  **QA Scenarios**:
  ```
  Scenario: Integration smoke test passes all checks
    Tool: Bash
    Preconditions: Backend + frontend dependencies installed, DB running
    Steps:
      1. Run .omo/integration-smoke.sh (or .ps1)
      2. Wait for completion
      3. Check exit code is 0
    Expected Result: All 10 checks pass
    Evidence: .omo/evidence/task-19-smoke-results.txt
  ```

  **Commit**: YES
  - Message: `test(voice): add integration smoke test script`
  - Files: `.omo/integration-smoke.ps1`
  - Pre-commit: `powershell -File .omo/integration-smoke.ps1`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, curl endpoint, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .omo/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `uv run mypy app/voice/ app/api/voice_router.py` (or `tsc --noEmit` for frontend). Run `ruff check app/voice/ app/api/voice_router.py`. Run `uv run pytest -q --tb=short`. Review all changed files for: `as any`/`@ts-ignore`, empty catches, console.log in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names (data/result/item/temp). Run `cd frontend && npx vite build` to verify frontend compiles.
  Output: `Backend lint [PASS/FAIL] | Frontend build [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high` (+ `playwright` skill if UI)
  Start from clean state. Execute smoke test script (`.omo/integration-smoke.ps1`). Run Playwright tests (`cd frontend && npx playwright test`). Verify all evidence files exist in `.omo/evidence/`. Test cross-task integration: backend routes registered, frontend builds, tests pass. Save to `.omo/evidence/final-qa/`.
  Output: `Smoke [N/N pass] | Playwright [N/N pass] | Evidence [N files] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Detect cross-task contamination: Task N touching Task M's files. Flag unaccounted changes. Check that NO file in `app/orchestrator/`, `app/reasoning/`, `app/api/chat_router.py`, `app/api/tools_router.py`, or existing `tests/` was modified.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

### Recommended Commit Grouping
Waves are independent — each wave can be committed separately.

**Wave 1 (Foundation)**
- Commit 1: `feat(voice): add voice schemas with AudioWorklet contract` — `app/schemas/voice.py`, `app/voice/__init__.py`
- Commit 2: `feat(voice): add Vertex AI support + update audio model to 2.5 Flash` — `app/config/settings.py`, `.env.example`
- Commit 3: `feat(voice): add voice_session_id + audio_duration columns, migration` — `app/db/models.py`, `migrations/versions/*.py`
- Commit 4: `test(voice): add Playwright infrastructure + MockWebSocket` — `frontend/playwright.config.ts`, `frontend/tests/__mocks__/websocket.ts`, `frontend/package.json`
- Commit 5: `feat(voice): add Gemini tool declarations + dispatch_tool` — `app/voice/tools.py`

**Wave 2 (Core Engine)**
- Commit 6: `feat(voice): add GeminiLiveSession + call summary + db_store + LLMClient Vertex AI` — `app/voice/session.py`, `app/voice/summary.py`, `app/memory/db_store.py`, `app/core/llm_client.py`, `app/api/deps.py`
- Commit 7: `feat(voice): add AudioWorklet resampler module` — `frontend/app/lib/audio-worklet.ts`, `frontend/public/audio-worklet-processor.js`

**Wave 3 (API + Frontend)**
- Commit 8: `feat(voice): add voice WebSocket router + app registration` — `app/api/voice_router.py`, `app/main.py`
- Commit 9: `feat(voice): add useVoiceSession hook` — `frontend/app/hooks/useVoiceSession.ts`
- Commit 10: `feat(voice): add VoiceInterface component` — `frontend/app/components/VoiceInterface.tsx`

**Wave 4 (Integration + Tests)**
- Commit 11: `feat(voice): add voice page, sidebar nav, and API client` — `frontend/app/routes/voice.tsx`, `frontend/app/router.tsx`, `frontend/app/components/Sidebar.tsx`, `frontend/app/lib/api-client.ts`
- Commit 12: `test(voice): add backend unit tests for all voice modules` — `tests/test_voice_*.py`
- Commit 13: `test(voice): add frontend unit + Playwright tests` — `frontend/tests/*.test.ts`, `frontend/tests/*.test.tsx`
- Commit 14: `test(voice): add integration smoke test script` — `.omo/integration-smoke.ps1`

### Pre-commit Hook
Before each commit, run:
```bash
uv run pytest -q --tb=short  # All tests must pass
cd frontend && npx vite build  # Frontend must compile
```

---

## Success Criteria

### Verification Commands
```bash
# 1. Health check
curl -s http://localhost:8000/health | python -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='ok'"

# 2. Ready check
curl -s http://localhost:8000/ready | python -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='ready'"

# 3. Existing text chat still works
curl -s -X POST http://localhost:8000/api/v1/chat/ \
  -H 'Content-Type: application/json' \
  -d '{"message": "Hello", "customer_id": "c63d2f89-9aa3-4157-8205-a7d6cfc23207"}' \
  | python -c "import sys,json; d=json.load(sys.stdin); assert 'response' in d"

# 4. Voice summary endpoint
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/voice/summary/test-id
# Expected: 404 (no session with that ID)

# 5. All tests pass
uv run pytest -q --tb=short
# Expected: 22 existing + ~20 new = ~42 tests, 0 failures

# 6. Frontend builds
cd frontend && npx vite build
# Expected: Build completes with no errors
```

### WebSocket Protocol Verification (Manual, with websocat)
```bash
# Requires authentication token - verify connection is rejected without one
# Expect: 403 close code
```

### Final Checklist
- [ ] All "Must Have" items present and working
- [ ] All "Must NOT Have" items absent (verify with grep)
- [ ] `gemini-2.0-flash-live-001` removed from all config files (grep check)
- [ ] No ScriptProcessorNode used (grep check)
- [ ] All 22 existing tests pass
- [ ] All ~20 new voice tests pass
- [ ] Frontend builds
- [ ] Integration smoke script passes all 10 checks
- [ ] Evidence files in `.omo/evidence/`
- [ ] User has given explicit "okay" after Final Verification Wave





