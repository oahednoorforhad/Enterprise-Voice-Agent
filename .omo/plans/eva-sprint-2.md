# EVA Sprint 2 - Retrieval Layer

## TL;DR

> **Quick Summary**: Build the 5 core Retrieval Layer Tool families (Customer, Billing, Ticket, Analytics, Knowledge) to expose enterprise data cleanly.
> 
> **Deliverables**: 
> - Shared `ToolResult` Pydantic response wrapper
> - 5 Tool Families (Python async functions returning Pydantic models)
> - FastAPI GET endpoints for all tools for debugging/testing
> - OpenRouter `httpx` embedding client integration
> 
> **Estimated Effort**: Large
> **Parallel Execution**: YES - 4 waves
> **Critical Path**: Task 1 (Shared models) → Task 2-5 (DB Tools) → Task 6 (OpenRouter config) → Task 7 (Knowledge Tool) → Task 8-12 (API endpoints)

---

## Context

### Original Request
Build Sprint 2 Retrieval Layer for the EVA MVP. Implement tools with raw Python functions returning Pydantic models, expose via FastAPI endpoints, use OpenRouter free embedding (`nomic-embed-text`), and limit historical data lists to the last 3 months.

### Interview Summary
**Key Discussions**:
- **Architecture**: Pristine Python functions returning Pydantic models (no ORM bloat).
- **Security**: Tools accept `customer_id` parameter to scope queries (LLM will eventually inject this context, HTTP endpoints will pass it from headers/query).
- **Embeddings**: OpenRouter `nomic-embed-text` explicitly chosen over Gemini.
- **Scope**: Analytics included. List queries bounded to 3 months.

### Metis Review
**Identified Gaps** (addressed):
- Added Test Strategy (TDD)
- OpenRouter conflict with Sprint 1 seed (resolved by updating config/settings.py but leaving Sprint 1 seed intact).
- Refund status in billing (will filter for `status='refunded'`).
- Added generic `ToolResult` model.

---

## Work Objectives

### Core Objective
Implement the 5 Retrieval Tool families as robust, fault-tolerant Python functions and expose them via FastAPI endpoints for agentic and manual QA.

### Concrete Deliverables
- `app/schemas/tools.py` with `ToolResult[T]` generic model
- `app/tools/customer/` (models, functions)
- `app/tools/billing/` (models, functions)
- `app/tools/ticket/` (models, functions)
- `app/tools/analytics/` (models, functions)
- `app/tools/knowledge/` (embedding client, models, functions)
- `app/api/` routers for all 5 tool families

### Definition of Done
- [ ] Pytest suite covers all tools (happy + edge cases)
- [ ] All 10 FastAPI endpoints callable via curl
- [ ] `SQLAlchemyError` correctly returns `ToolResult(success=False, error=...)`

### Must Have
- Every data query MUST filter by `customer_id`.
- List queries MUST filter `created_at >= NOW() - 3 months`.
- OpenRouter integration MUST use `httpx`.
- All tools MUST return Pydantic models.

### Must NOT Have (Guardrails)
- Do NOT raise exceptions for data not found (return `ToolResult` with error).
- Do NOT build an LLM orchestration loop in this sprint.
- Do NOT build real Auth.

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES
- **Automated tests**: TDD
- **Framework**: pytest (with testcontainers)
- Each task includes Pytest setup and Agent-Executed QA Scenarios via `curl`.

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.omo/evidence/task-{N}-{scenario-slug}.{ext}`.

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately - Foundation):
├── Task 1: Shared ToolResult Schema [quick]

Wave 2 (DB Tools - MAX PARALLEL):
├── Task 2: Customer Tool [unspecified-high]
├── Task 3: Billing Tool [unspecified-high]
├── Task 4: Ticket Tool [unspecified-high]
└── Task 5: Analytics Tool [unspecified-high]

Wave 3 (Knowledge & API config):
├── Task 6: OpenRouter Client & Config [unspecified-high]
├── Task 7: Knowledge Tool (depends on 6) [unspecified-high]
├── Task 8: FastAPI Router setup [quick]

Wave 4 (API Endpoints - MAX PARALLEL):
├── Task 9: Customer & Billing Endpoints (depends on 2, 3, 8) [unspecified-high]
├── Task 10: Ticket & Analytics Endpoints (depends on 4, 5, 8) [unspecified-high]
└── Task 11: Knowledge Endpoints (depends on 7, 8) [unspecified-high]

Wave FINAL:
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)
```

---

## TODOs

- [ ] 1. Shared ToolResult Schema

  **What to do**:
  - Create `app/schemas/tools.py`.
  - Define `class ToolResult(BaseModel, Generic[T])` with fields `success: bool`, `data: T | None`, `error: str | None`.
  - Add helper classmethods `def ok(cls, data: T)` and `def fail(cls, error: str)`.
  - Write test in `tests/test_tools.py` verifying serialization.

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple standalone Pydantic model.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: 2, 3, 4, 5, 7
  - **Blocked By**: None

  **References**:
  - `app/schemas/`: Existing schemas directory.

  **Acceptance Criteria**:
  - [ ] `ToolResult.ok({"id": 1}).success` is True.

  **QA Scenarios**:
  ```
  Scenario: Validate ToolResult serialization
    Tool: interactive_bash
    Preconditions: None
    Steps:
      1. uv run python -c "from app.schemas.tools import ToolResult; print(ToolResult.ok('test').model_dump_json())"
    Expected Result: Output is exactly {"success":true,"data":"test","error":null}
    Evidence: .omo/evidence/task-1-serialization.txt
  ```

- [ ] 2. Customer Tool

  **What to do**:
  - Create `app/tools/customer/models.py`: `CustomerProfile` and `SubscriptionStatus` schemas.
  - Create `app/tools/customer/functions.py`: `async def get_customer_profile(session: AsyncSession, customer_id: UUID) -> ToolResult[CustomerProfile]` and `async def get_subscription_status(session: AsyncSession, customer_id: UUID) -> ToolResult[SubscriptionStatus]`.
  - Queries must catch DB exceptions and return `ToolResult.fail()`.
  - Tests in `tests/test_tool_customer.py` using DB testcontainers.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: DB integration and Pytest fixtures.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: 9
  - **Blocked By**: 1

  **References**:
  - `app/db/models.py:Customer`
  - `app/db/models.py:Subscription`

  **Acceptance Criteria**:
  - [ ] DB error gracefully returns `success=False` with error string.

  **QA Scenarios**:
  ```
  Scenario: Test Python function returns valid profile
    Tool: interactive_bash
    Preconditions: Seeded test DB
    Steps:
      1. Run pytest tests/test_tool_customer.py -v
    Expected Result: Tests pass (1 happy, 1 edge case)
    Evidence: .omo/evidence/task-2-pytest.txt
  ```

- [ ] 3. Billing Tool

  **What to do**:
  - Create `app/tools/billing/models.py`: `BillingRecordModel` schema.
  - Create `app/tools/billing/functions.py`: 
    - `get_billing_history(session, customer_id)` -> returns records from last 3 months.
    - `get_refund_history(session, customer_id)` -> returns records from last 3 months where `status == 'refunded'`.
  - Filter logic: `BillingRecord.created_at >= datetime.utcnow() - timedelta(days=90)`.
  - Tests in `tests/test_tool_billing.py`.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Time-based filtering and ORM logic.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: 9
  -   **Blocked By**: 1

  **Acceptance Criteria**:
  - [ ] `get_billing_history` only returns records <= 90 days old.
  - [ ] `get_refund_history` only returns records with status `refunded`.

  **QA Scenarios**:
  ```
  Scenario: Test Python function returns last 3 months
    Tool: interactive_bash
    Preconditions: Seeded test DB
    Steps:
      1. Run pytest tests/test_tool_billing.py -v
    Expected Result: Tests pass (1 happy, 1 edge case)
    Evidence: .omo/evidence/task-3-pytest.txt
  ```

- [ ] 4. Ticket Tool

  **What to do**:
  - Create `app/tools/ticket/models.py`: `TicketModel` schema.
  - Create `app/tools/ticket/functions.py`:
    - `get_support_tickets(session, customer_id)` -> from last 3 months.
    - `get_ticket_status(session, customer_id, ticket_id)` -> single ticket, must enforce customer_id.
  - Filter logic for dates and exact match.
  - Tests in `tests/test_tool_ticket.py`.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: 10
  -   **Blocked By**: 1

  **Acceptance Criteria**:
  - [ ] `get_ticket_status` for a ticket belonging to a different customer returns `success=False`.

  **QA Scenarios**:
  ```
  Scenario: Ticket isolation test
    Tool: interactive_bash
    Preconditions: None
    Steps:
      1. Run pytest tests/test_tool_ticket.py -k "isolation"
    Expected Result: Querying another user's ticket_id returns error.
    Evidence: .omo/evidence/task-4-isolation.txt
  ```

- [ ] 5. Analytics Tool

  **What to do**:
  - Create `app/tools/analytics/models.py`: `UsageAnalyticModel` schema.
  - Create `app/tools/analytics/functions.py`:
    - `get_usage_analytics(session, customer_id, metric_name: str | None = None)` -> returns raw rows from last 3 months.
  - Tests in `tests/test_tool_analytics.py`.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: 10
  -   **Blocked By**: 1

  **Acceptance Criteria**:
  - [ ] `get_usage_analytics` filters correctly by `metric_name` when provided.

  **QA Scenarios**:
  ```
  Scenario: Analytics query with optional metric
    Tool: interactive_bash
    Preconditions: None
    Steps:
      1. Run pytest tests/test_tool_analytics.py -v
    Expected Result: Passes happy and empty scenarios.
    Evidence: .omo/evidence/task-5-pytest.txt
  ```

- [ ] 6. OpenRouter Client & Config

  **What to do**:
  - Update `app/config/settings.py` and `.env.example` to add: `OPENROUTER_API_KEY` (default ""), `OPENROUTER_BASE_URL` (default `https://openrouter.ai/api/v1`), `OPENROUTER_EMBEDDING_MODEL` (default `nomic-embed-text`).
  - Create `app/tools/knowledge/embedding_client.py` using `httpx.AsyncClient`.
  - Export `async def get_embedding(text: str) -> list[float]`. Must catch `httpx.HTTPError`.
  - Write test utilizing `pytest-httpx` or mocking.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: HTTP client mocking and env config.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3
  - **Blocks**: 7
  -   **Blocked By**: None

  **Acceptance Criteria**:
  - [ ] `get_embedding` returns a list of exactly 768 floats for `nomic-embed-text`.
  - [ ] httpx errors are caught and re-raised as custom exceptions or returned as errors.

  **QA Scenarios**:
  ```
  Scenario: OpenRouter client handles timeout
    Tool: interactive_bash
    Preconditions: None
    Steps:
      1. Run pytest tests/test_embedding_client.py -k "timeout"
    Expected Result: Client gracefully returns error or raises specific handled exception.
    Evidence: .omo/evidence/task-6-timeout.txt
  ```

- [ ] 7. Knowledge Tool

  **What to do**:
  - Create `app/tools/knowledge/models.py`: `KnowledgeResult` schema.
  - Create `app/tools/knowledge/functions.py`:
    - `search_documentation(session, query: str)` -> uses embedding_client, queries VectorStore for collection `documentation`, LIMIT 5.
    - `search_policies(session, query: str)` -> same but for `policies` collection.
  - Uses `VectorStore.search` from Sprint 1. Returns `ToolResult`.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3
  - **Blocks**: 11
  -   **Blocked By**: 1, 6

  **Acceptance Criteria**:
  - [ ] `search_documentation` only queries the `documentation` collection.
  - [ ] `search_policies` only queries the `policies` collection.

  **QA Scenarios**:
  ```
  Scenario: Search with valid query
    Tool: interactive_bash
    Preconditions: Mocked embedding client
    Steps:
      1. Run pytest tests/test_tool_knowledge.py -v
    Expected Result: Calls VectorStore and maps results to ToolResult.
    Evidence: .omo/evidence/task-7-pytest.txt
  ```

- [ ] 8. FastAPI Router Setup

  **What to do**:
  - Create `app/api/tools_router.py`.
  - Create the base router: `tools_router = APIRouter(prefix="/api/v1/tools", tags=["Tools"])`.
  - Add to `app/main.py`.

  **Recommended Agent Profile**:
  - **Category**: `quick`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3
  - **Blocks**: 9, 10, 11
  -   **Blocked By**: None

  **Acceptance Criteria**:
  - [ ] Router is successfully included in the main FastAPI app.

  **QA Scenarios**:
  ```
  Scenario: Router mounts successfully
    Tool: bash
    Preconditions: FastAPI running
    Steps:
      1. curl http://localhost:8000/docs | grep "/api/v1/tools"
    Expected Result: Route path is found in OpenAPI spec.
    Evidence: .omo/evidence/task-8-router.txt
  ```

- [ ] 9. Customer & Billing Endpoints

  **What to do**:
  - Create GET endpoints in `app/api/tools_customer.py` and `app/api/tools_billing.py` (or directly in `tools_router.py`).
  - E.g. `GET /api/v1/tools/customer/profile?customer_id=UUID`.
  - Must call the tool functions and return `ToolResult` directly.
  - No DB logic here, just calling functions.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4
  -   **Blocked By**: 2, 3, 8

  **Acceptance Criteria**:
  - [ ] Customer profile endpoint returns HTTP 200 with `ToolResult` JSON (even if customer not found).
  - [ ] Missing `customer_id` query param returns FastAPI 422 validation error.

  **QA Scenarios**:
  ```
  Scenario: Customer HTTP endpoint happy path
    Tool: bash
    Preconditions: uvicorn running
    Steps:
      1. curl -s "http://localhost:8000/api/v1/tools/customer/profile?customer_id=00000000-0000-0000-0000-000000000000"
    Expected Result: JSON with success=false, error="Customer not found"
    Evidence: .omo/evidence/task-9-curl.txt
  ```

- [ ] 10. Ticket & Analytics Endpoints

  **What to do**:
  - Create GET endpoints for tickets and analytics.
  - Same pattern as task 9.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4
  -   **Blocked By**: 4, 5, 8

  **Acceptance Criteria**:
  - [ ] Endpoints accept `customer_id` and return `ToolResult` JSON.

  **QA Scenarios**:
  ```
  Scenario: Ticket HTTP endpoint
    Tool: bash
    Preconditions: uvicorn running
    Steps:
      1. curl -s "http://localhost:8000/api/v1/tools/ticket/list?customer_id=..."
    Expected Result: Valid JSON matching ToolResult structure.
    Evidence: .omo/evidence/task-10-curl.txt
  ```

- [ ] 11. Knowledge Endpoints

  **What to do**:
  - Create GET endpoints for documentation and policies.
  - Needs `query` parameter instead of `customer_id`.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4
  -   **Blocked By**: 7, 8

  **Acceptance Criteria**:
  - [ ] Endpoints accept `query` string and return `ToolResult` JSON.

  **QA Scenarios**:
  ```
  Scenario: Knowledge HTTP endpoint
    Tool: bash
    Preconditions: uvicorn running
    Steps:
      1. curl -s "http://localhost:8000/api/v1/tools/knowledge/documentation?query=refund"
    Expected Result: Valid JSON response.
    Evidence: .omo/evidence/task-11-curl.txt
  ```

---

## Final Verification Wave

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read plan end-to-end. For each "Must Have": verify implementation exists. For each "Must NOT Have": grep codebase for forbidden patterns. Check evidence files exist in .omo/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `uv run ruff check` + `uv run pytest -q`. Review all changed files for: `as any`/`@ts-ignore`, empty catches. Check AI slop: excessive comments, over-abstraction.
  Output: `Build [PASS/FAIL] | Lint [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Save to `.omo/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Detect cross-task contamination. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **1**: `type(scope): desc` - file.ts, npm test

---

## Success Criteria

### Verification Commands
```bash
uv run pytest -v  # Expected: All tests pass
uv run ruff check app/ scripts/ tests/  # Expected: clean
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass
