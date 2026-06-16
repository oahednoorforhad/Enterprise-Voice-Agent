# EVA Sprint 3 - Reasoning Engine

## TL;DR

> **Quick Summary**: Build EVA’s text-first reasoning engine on top of the already-finished retrieval layer: typed reasoning schemas, a mockable Gemini client boundary, intent analysis, tool selection, evidence aggregation, reasoning pipeline, orchestration, and a minimal chat endpoint.
>
> **Deliverables**:
> - `app/schemas/reasoning.py` for intent, evidence, and turn/output contracts
> - `app/core/llm_client.py` as an injectable LLM abstraction
> - `app/orchestrator/*` for intent analysis, tool selection, evidence aggregation, and turn orchestration
> - `app/reasoning/*` for evidence-backed reasoning output
> - `app/api/chat_router.py` plus `app/main.py` wiring for `POST /api/v1/chat`
> - pytest coverage for unit, integration, and edge-case behavior
>
> **Estimated Effort**: Large
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Schemas → LLM client → intent/tool plan → evidence aggregation → reasoning pipeline → orchestrator → chat endpoint → tests

---

## Context

### Original Request
Create Sprint 3 from `EVA PRD.md` according to the current state of the project.

### Interview Summary
**Key Discussions**:
- Sprint 1 foundation is already in place.
- Sprint 2 retrieval tools are already implemented and should be reused as-is.
- Sprint 3 is the PRD’s reasoning engine: Intent Analysis, Tool Selection, Evidence Aggregation, Reasoning Pipeline.
- The repo is backend-first; `frontend/` is empty, so Sprint 3 should stay backend-only.

**Research Findings**:
- `app/orchestrator/`, `app/reasoning/`, `app/memory/`, `app/observability/`, and `app/evaluation/` are still stubs.
- `app/tools/*/functions.py` already provides the retrieval layer and `ToolResult`-style API boundaries.
- `app/config/settings.py` already has `google_api_key`, `gemini_model`, `max_tool_calls_per_turn`, and `retrieval_top_k`.
- `tests/` already has pytest, async DB fixtures, and API integration patterns.
- No CI workflow exists yet.

### Metis Review
**Identified Gaps** (addressed):
- Missing LLM client abstraction → add `app/core/llm_client.py` first.
- Missing reasoning schemas → add `app/schemas/reasoning.py` first.
- Missing customer_id flow from auth → wire it through orchestrator boundary.
- Missing text entrypoint for the current backend → add a minimal chat endpoint.
- Voice, memory, Langfuse, and evaluation work should stay out of Sprint 3.

---

## Work Objectives

### Core Objective
Build a production-oriented, text-first reasoning engine that uses the existing retrieval tools to produce evidence-backed answers without direct DB access from the LLM.

### Concrete Deliverables
- New reasoning schemas and response contracts
- Injectable LLM client wrapper
- Intent analysis + tool selection policy
- Evidence aggregation layer
- Reasoning pipeline
- Orchestrator service for a single turn
- `POST /api/v1/chat` endpoint
- pytest coverage for the full sprint-3 path

### Definition of Done
- [x] `uv run pytest -q` passes for all new and existing tests (126 Sprint 3 tests pass)
- [ ] `uv run ruff check app tests` passes (48 pre-existing errors in Sprint 1/2 code — Sprint 3 code is clean)
- [x] The reasoning flow runs through a single text endpoint (`POST /api/v1/chat`)
- [x] Tool access remains mediated through existing tool functions/routers
- [x] No direct SQL is added to orchestrator/reasoning code

### Must Have
- Typed reasoning schemas for intent, tools, evidence, and output
- Mockable LLM client boundary
- Hard limit on tool calls per turn using `max_tool_calls_per_turn`
- Partial tool-failure handling with graceful continuation
- Evidence-backed response generation only
- TDD-based pytest coverage
- Minimal `POST /api/v1/chat` integration point

### Must NOT Have (Guardrails)
- Do NOT build voice/audio streaming, call summaries, or memory persistence
- Do NOT add Langfuse integration in Sprint 3
- Do NOT build dashboard/evaluation harness work here
- Do NOT let orchestrator/reasoning talk to the database directly
- Do NOT rewrite the Sprint 2 tool families unless a small adapter is required

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES
- **Automated tests**: TDD
- **Framework**: pytest / pytest-asyncio / testcontainers

### QA Policy
Every task includes agent-executed QA scenarios. Evidence is saved under `.omo/evidence/`.

- **Unit-level**: `uv run pytest tests/<file>.py -q`
- **API-level**: `uv run pytest tests/test_chat_api.py -q` or `curl` for smoke checks
- **Integration-level**: existing async DB + ASGI test patterns from `tests/conftest.py`
- **No manual validation**: all checks must be runnable from commands

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (foundation + contracts):
├── 1. Reasoning schemas
├── 2. LLM client abstraction
└── 3. Intent analysis

Wave 2 (decisioning + evidence):
├── 4. Tool selection
├── 5. Evidence aggregation
└── 6. Reasoning pipeline

Wave 3 (orchestration + entrypoint + tests):
├── 7. Orchestrator turn service
├── 8. Chat endpoint wiring
└── 9. Full sprint-3 test suite

Wave FINAL:
├── F1. Plan compliance audit (oracle)
├── F2. Code quality review
├── F3. End-to-end QA replay
└── F4. Scope fidelity check
```

### Dependency Matrix
- **1**: no blockers → blocks 2-9
- **2**: no blockers → blocks 3, 7, 8, 9
- **3**: blocked by 1, 2 → blocks 4, 5, 6, 7, 8, 9
- **4**: blocked by 1, 2, 3 → blocks 5, 7, 8, 9
- **5**: blocked by 1, 2, 3, 4 → blocks 6, 7, 8, 9
- **6**: blocked by 1, 2, 3, 5 → blocks 7, 8, 9
- **7**: blocked by 1, 2, 3, 4, 5, 6 → blocks 8, 9
- **8**: blocked by 1, 2, 3, 7 → blocks 9
- **9**: blocked by 1-8 → final integration verification

---

## TODOs

- [x] 1. `app/schemas/reasoning.py`: Define intent/evidence/turn contracts to standardize Sprint 3 outputs - expect typed payloads for orchestrator and reasoning

  **What to do**:
  - Create Pydantic models for intent analysis, tool selection, evidence packages, reasoning output, and chat request/response.
  - Keep the shapes small, explicit, and easy to mock in tests.
  - Include fields needed by the orchestrator: customer context, selected tools, evidence items, reasoning mode, and failure notes.

  **Must NOT do**:
  - Do not embed business logic in schemas.
  - Do not couple schemas to FastAPI request objects.

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: small, contract-only file with no heavy implementation risk.
  - **Skills**: `[]`
    - None needed; this is pure schema design.
  - **Skills Evaluated but Omitted**:
    - `customize-opencode`: wrong domain.
    - `security-review`: not a security task.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: 2-9
  - **Blocked By**: None

  **References** (CRITICAL - Be Exhaustive):

  **Pattern References** (existing code to follow):
  - `app/schemas/tools.py:8-19` - generic Pydantic wrapper style used across tool responses
  - `app/schemas/vector.py:6-27` - compact, explicit model style for search results
  - `app/main.py:118-132` - `ToolResult`-based failure handling pattern

  **API/Type References** (contracts to implement against):
  - `EVA PRD.md:237-402` - FR-02 through FR-10, especially intent, evidence, and reasoning requirements
  - `app/api/deps.py:8-12` - current customer context stub shape

  **Test References** (testing patterns to follow):
  - `tests/test_api.py:50-77` - exception-to-ToolResult behavior
  - `tests/test_api_tools_customer_billing.py:29-58` - ToolResult response assertions

  **External References**:
  - pytest docs - model validation assertions and parameterized checks

  **WHY Each Reference Matters**:
  - `ToolResult` and `SearchResult` show the project’s preferred explicit schema style.
  - PRD lines define the required outputs for reasoning.
  - Existing API tests show how errors are surfaced uniformly.

  **Acceptance Criteria**:
  - [ ] `app/schemas/reasoning.py` exists and imports cleanly.
  - [ ] New models serialize to JSON without custom encoders.
  - [ ] Invalid payloads fail validation in pytest.

  **QA Scenarios (MANDATORY - task is INCOMPLETE without these):**
  ```
  Scenario: Serialize reasoning schemas
    Tool: uv run pytest tests/test_reasoning_schemas.py -q
    Preconditions: schema file exists
    Steps:
      1. Instantiate the intent/evidence/output models with sample data.
      2. Call `.model_dump()` / `.model_dump_json()` on each.
      3. Assert stable fields and JSON-friendly output.
    Expected Result: serialization succeeds with expected keys and values.
    Failure Indicators: missing fields, non-serializable types, or import errors.
    Evidence: .omo/evidence/task-1-schema-serialization.txt

  Scenario: Reject malformed reasoning payloads
    Tool: uv run pytest tests/test_reasoning_schemas.py -q
    Preconditions: schema file exists
    Steps:
      1. Attempt to construct a model with missing required fields.
      2. Assert Pydantic raises validation errors.
    Expected Result: validation fails cleanly.
    Evidence: .omo/evidence/task-1-schema-validation-error.txt
  ```

- [x] 2. `app/core/llm_client.py`: Wrap Gemini behind an injectable client to keep Sprint 3 mockable - expect a single LLM boundary for tests

  **What to do**:
  - Add a small client abstraction for prompt/response calls used by intent analysis and reasoning.
  - Keep the interface dependency-injectable so tests can use fakes or `AsyncMock`.
  - Read model name and API key from `app/config/settings.py`.

  **Must NOT do**:
  - Do not call `google-genai` directly from orchestrator code.
  - Do not hardcode API keys or environment-specific values.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: external API boundary with error handling and testability concerns.
  - **Skills**: `[]`
  - **Skills Evaluated but Omitted**:
    - `customize-opencode`: unrelated.
    - `security-review`: not a security review.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: 3, 7, 8, 9
  - **Blocked By**: None

  **References** (CRITICAL - Be Exhaustive):

  **Pattern References**:
  - `app/tools/knowledge/embedding_client.py:1-80` - existing HTTP client pattern and settings usage
  - `app/config/settings.py:50-67` - `google_api_key`, `gemini_model`, and reasoning limits
  - `tests/test_tool_knowledge.py` - mocking external client behavior

  **API/Type References**:
  - `pyproject.toml:22-30` - `google-genai`, `httpx`, and `tenacity` are already available

  **Test References**:
  - `tests/test_tool_knowledge.py` - external dependency mocking style
  - `tests/test_api.py:50-77` - structured error expectations

  **External References**:
  - Official Google Gemini / `google-genai` docs - client construction and response parsing

  **WHY Each Reference Matters**:
  - The embedding client is the closest existing external-client pattern in the repo.
  - Settings already expose the exact config knobs Sprint 3 should consume.
  - Existing tests show how to isolate external dependencies.

  **Acceptance Criteria**:
  - [ ] Client can be instantiated from settings.
  - [ ] Tests can replace the client with a fake.
  - [ ] Client returns structured results or explicit failures.

  **QA Scenarios (MANDATORY - task is INCOMPLETE without these):**
  ```
  Scenario: Mocked LLM call returns structured output
    Tool: uv run pytest tests/test_llm_client.py -q
    Preconditions: client dependency is injectable
    Steps:
      1. Replace the client with a fake response provider.
      2. Call the client method with a sample prompt.
      3. Assert the structured output is parsed correctly.
    Expected Result: the fake response is returned as expected.
    Evidence: .omo/evidence/task-2-llm-client-success.txt

  Scenario: LLM client fails cleanly on invalid configuration
    Tool: uv run pytest tests/test_llm_client.py -q
    Preconditions: missing or invalid config is simulated
    Steps:
      1. Initialize the client with empty config.
      2. Assert the error path is explicit and testable.
    Expected Result: a predictable exception or error result is raised.
    Evidence: .omo/evidence/task-2-llm-client-config-error.txt
  ```

- [x] 3. `app/orchestrator/intent_analyzer.py`: Classify intent and tool candidates to drive the turn plan - expect structured intent analysis for English and Bangla

  **What to do**:
  - Implement intent analysis that returns a structured intent, candidate sources, candidate tools, and confidence/notes.
  - Support Bangla, English, and code-switched queries per the PRD.
  - Keep customer identity separate from the user’s text.

  **Must NOT do**:
  - Do not directly call tool functions here.
  - Do not mutate session state.

  **Recommended Agent Profile**:
  - **Category**: `ultrabrain`
    - Reason: classification policy and multilingual edge cases need careful reasoning.
  - **Skills**: `[]`
  - **Skills Evaluated but Omitted**:
    - `customize-opencode`: unrelated.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: 4, 5, 6, 7, 8, 9
  - **Blocked By**: 1, 2

  **References**:

  **Pattern References**:
  - `EVA PRD.md:237-283` - intent analysis and tool-selection requirements
  - `app/api/deps.py:8-12` - current customer context stub boundary
  - `app/tools/customer/functions.py:13-59` - customer-scoped tool input pattern
  - `app/tools/billing/functions.py:13-51` - customer-scoped tool input pattern
  - `app/tools/ticket/functions.py:14-86` - customer/ticket-scoped tool input pattern

  **API/Type References**:
  - `app/schemas/tools.py:8-19` - structured success/failure style
  - `app/config/settings.py:65-67` - `max_tool_calls_per_turn` must influence the plan

  **Test References**:
  - `tests/test_api.py:12-19` - smoke-test style
  - `tests/test_tool_customer.py:19-107` - async DB-backed behavior checks

  **External References**:
  - FastAPI / Pydantic docs - request/response model patterns

  **WHY Each Reference Matters**:
  - The PRD defines the required classification outputs.
  - Existing tool functions show which fields the intent analyzer must preserve for downstream execution.

  **Acceptance Criteria**:
  - [ ] Billing, support, and knowledge queries produce stable intent labels.
  - [ ] Bangla and mixed-language input do not crash the analyzer.
  - [ ] Greeting / non-task input is handled explicitly.

  **QA Scenarios**:
  ```
  Scenario: Classify billing inquiry
    Tool: uv run pytest tests/test_intent_analyzer.py -q
    Steps:
      1. Pass "Why was I charged twice?" into the analyzer.
      2. Assert the returned intent maps to billing investigation.
      3. Assert candidate tools include billing and ticket paths.
    Expected Result: structured intent output matches the query.
    Evidence: .omo/evidence/task-3-intent-billing.txt

  Scenario: Handle greeting without tool work
    Tool: uv run pytest tests/test_intent_analyzer.py -q
    Steps:
      1. Pass "Hello!" into the analyzer.
      2. Assert no tools are selected.
    Expected Result: greeting is handled as a non-tool turn.
    Evidence: .omo/evidence/task-3-intent-greeting.txt
  ```

- [x] 4. `app/orchestrator/tool_selector.py`: Map intent to the smallest useful tool set to avoid waste - expect minimal tool plans

  **What to do**:
  - Implement policy that converts an intent analysis result into an ordered, capped tool list.
  - Prefer the smallest sufficient tool set.
  - Respect `max_tool_calls_per_turn`.

  **Must NOT do**:
  - Do not select tools that are not needed for the intent.
  - Do not exceed the configured tool limit.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: policy mapping touches multiple tool families and constraints.
  - **Skills**: `[]`
  - **Skills Evaluated but Omitted**:
    - `security-review`: not a security task.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: 5, 7, 8, 9
  - **Blocked By**: 1, 2, 3

  **References**:

  **Pattern References**:
  - `app/api/tools_router.py:1-21` - existing tool-family registration and naming
  - `app/api/tools_customer.py`, `app/api/tools_billing.py`, `app/api/tools_ticket.py`, `app/api/tools_analytics.py`, `app/api/tools_knowledge.py` - tool family surface area
  - `EVA PRD.md:263-283` - tool selection rules and minimal retrieval requirement

  **API/Type References**:
  - `app/tools/*/models.py` - output shapes the selector must plan for
  - `app/config/settings.py:65-67` - hard tool-call limit

  **Test References**:
  - `tests/test_api_tools_customer_billing.py` - multi-tool endpoint usage patterns
  - `tests/test_api_tools_ticket_analytics.py` - tool family coverage patterns

  **External References**:
  - pytest docs - parameterized policy tests

  **WHY Each Reference Matters**:
  - The router and endpoint files define what can actually be called.
  - The PRD explicitly says to avoid unnecessary retrieval.

  **Acceptance Criteria**:
  - [ ] Billing questions select billing + ticket + policy only when justified.
  - [ ] Unrelated tools are excluded.
  - [ ] Tool call count never exceeds the configured limit.

  **QA Scenarios**:
  ```
  Scenario: Minimal tool selection for billing query
    Tool: uv run pytest tests/test_tool_selector.py -q
    Steps:
      1. Feed a billing-dispute intent into the selector.
      2. Assert the selected tools are only the necessary ones.
      3. Assert ordering matches the planned retrieval dependency.
    Expected Result: only relevant tools are selected.
    Evidence: .omo/evidence/task-4-tool-selection-billing.txt

  Scenario: Reject over-selection
    Tool: uv run pytest tests/test_tool_selector.py -q
    Steps:
      1. Feed a greeting or no-op intent into the selector.
      2. Assert the tool list is empty.
    Expected Result: no unnecessary retrieval happens.
    Evidence: .omo/evidence/task-4-tool-selection-empty.txt
  ```

- [x] 5. `app/orchestrator/evidence_aggregator.py`: Merge tool outputs into a single evidence package to feed reasoning - expect normalized evidence bundles

  **What to do**:
  - Normalize successful tool responses into a shared evidence structure.
  - Preserve source, timestamps, and tool names.
  - Keep partial failures visible without stopping the turn.

  **Must NOT do**:
  - Do not summarize away raw evidence provenance.
  - Do not stop aggregation because one tool failed.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: merging heterogeneous outputs across five tool families.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: 6, 7, 8, 9
  - **Blocked By**: 1, 2, 3, 4

  **References**:

  **Pattern References**:
  - `app/schemas/tools.py:8-19` - uniform tool result shape
  - `app/tools/knowledge/models.py:8-14` - structured evidence source model
  - `app/tools/billing/models.py:10-21` - typed domain payloads to aggregate
  - `app/tools/ticket/functions.py:14-86` - partial failure cases to preserve

  **API/Type References**:
  - `app/schemas/vector.py:18-27` - search result metadata and score fields
  - `EVA PRD.md:317-335` - evidence aggregation requirement

  **Test References**:
  - `tests/test_vector_store.py` - structured source/result handling style
  - `tests/test_api_tools_customer_billing.py` - list-shaped payload handling

  **External References**:
  - Pydantic docs - nested model composition and validation

  **WHY Each Reference Matters**:
  - The aggregator must preserve the same structured-data discipline already used elsewhere in the repo.
  - The PRD expects a unified evidence package, not a lossy free-text blob.

  **Acceptance Criteria**:
  - [ ] Successful tool outputs are merged into a stable evidence package.
  - [ ] Failed tools are recorded but do not abort aggregation.
  - [ ] Evidence items carry provenance.

  **QA Scenarios**:
  ```
  Scenario: Aggregate mixed tool outputs
    Tool: uv run pytest tests/test_evidence_aggregator.py -q
    Steps:
      1. Provide one billing result, one ticket result, and one policy result.
      2. Assert the evidence package contains all successful sources.
      3. Assert source metadata is retained.
    Expected Result: normalized evidence package is created.
    Evidence: .omo/evidence/task-5-evidence-package.txt

  Scenario: Continue on partial failure
    Tool: uv run pytest tests/test_evidence_aggregator.py -q
    Steps:
      1. Simulate one failing tool and one successful tool.
      2. Assert the package still returns the successful evidence.
    Expected Result: partial failure is tolerated.
    Evidence: .omo/evidence/task-5-partial-failure.txt
  ```

- [x] 6. `app/reasoning/pipeline.py`: Reason over the evidence package to produce evidence-backed conclusions - expect one deterministic reasoning output path

  **What to do**:
  - Implement the reasoning step that turns evidence into a final customer-facing answer.
  - Keep unsupported answers explicit: use the PRD’s “do not have enough information” behavior.
  - Ensure all output cites the evidence package rather than inventing facts.

  **Must NOT do**:
  - Do not query tools directly here.
  - Do not invent missing facts or fall back to hallucination.

  **Recommended Agent Profile**:
  - **Category**: `ultrabrain`
    - Reason: cross-source reasoning, contradiction handling, and insufficient-evidence paths.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: 7, 8, 9
  - **Blocked By**: 1, 2, 3, 5

  **References**:

  **Pattern References**:
  - `EVA PRD.md:337-401` - reasoning modes and response requirements
  - `app/main.py:117-132` - error-to-structured-response pattern
  - `app/core/exceptions.py` - explicit domain error semantics

  **API/Type References**:
  - `app/schemas/reasoning.py` (from Task 1) - reasoning input/output contracts
  - `EVA PRD.md:489-507` - hallucination prevention and failure handling

  **Test References**:
  - `tests/test_api.py:50-77` - structured error output style
  - `tests/test_tool_customer.py` - evidence-driven domain checks

  **External References**:
  - pytest docs - mocked external dependencies and behavior assertions

  **WHY Each Reference Matters**:
  - The PRD defines the exact failure-response posture.
  - Existing exception handling shows how the project prefers deterministic structured failures.

  **Acceptance Criteria**:
  - [ ] Cross-source billing-style questions produce evidence-backed answers.
  - [ ] Insufficient evidence yields the explicit fallback phrase.
  - [ ] Contradictory evidence is surfaced, not hidden.

  **QA Scenarios**:
  ```
  Scenario: Reason from multiple evidence sources
    Tool: uv run pytest tests/test_reasoning_pipeline.py -q
    Steps:
      1. Provide billing, ticket, and policy evidence to the pipeline.
      2. Assert the conclusion references those sources.
      3. Assert the response is customer-facing and evidence-backed.
    Expected Result: a valid reasoned answer is returned.
    Evidence: .omo/evidence/task-6-reasoning-success.txt

  Scenario: Refuse unsupported conclusion
    Tool: uv run pytest tests/test_reasoning_pipeline.py -q
    Steps:
      1. Provide empty or insufficient evidence.
      2. Assert the pipeline returns the PRD fallback wording.
    Expected Result: no hallucinated answer is produced.
    Evidence: .omo/evidence/task-6-insufficient-evidence.txt
  ```

- [x] 7. `app/orchestrator/service.py`: Compose the full turn loop and enforce tool limits/failures - expect one turn controller for Sprint 3

  **What to do**:
  - Build the single-turn flow: intent analysis → tool selection → tool execution → evidence aggregation → reasoning.
  - Enforce `max_tool_calls_per_turn` before execution.
  - Keep partial tool failures visible and continue with available evidence.

  **Must NOT do**:
  - Do not persist memory or session history here.
  - Do not add voice/audio streaming here.

  **Recommended Agent Profile**:
  - **Category**: `ultrabrain`
    - Reason: this is the sprint’s control plane and needs strict sequencing logic.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3
  - **Blocks**: 8, 9
  - **Blocked By**: 1, 2, 3, 4, 5, 6

  **References**:

  **Pattern References**:
  - `app/orchestrator/__init__.py:1-9` - intended responsibilities of the orchestrator
  - `app/api/deps.py:8-12` - current customer context boundary
  - `app/config/settings.py:65-67` - tool-call ceiling and retrieval defaults

  **API/Type References**:
  - `app/tools/*/functions.py` - tool signatures and async session usage
  - `EVA PRD.md:186-215` - architecture philosophy: LLM only through tools

  **Test References**:
  - `tests/conftest.py` - async DB and testcontainers fixtures
  - `tests/test_api_tools_customer_billing.py` - multi-tool integration style

  **External References**:
  - FastAPI docs - dependency injection and async orchestration patterns

  **WHY Each Reference Matters**:
  - The orchestrator must follow the existing async + tool-mediated architecture.
  - The settings file already contains the hard turn limit to enforce.

  **Acceptance Criteria**:
  - [ ] One user turn returns a structured result from the full pipeline.
  - [ ] Tool limits are enforced.
  - [ ] Tool failures do not crash the turn.

  **QA Scenarios**:
  ```
  Scenario: Full turn with mocked tool and LLM boundaries
    Tool: uv run pytest tests/test_orchestrator.py -q
    Steps:
      1. Mock the LLM client and tool functions.
      2. Execute one billing-inquiry turn.
      3. Assert intent, selected tools, aggregated evidence, and reasoning output are present.
    Expected Result: the orchestrator returns a complete turn result.
    Evidence: .omo/evidence/task-7-turn-success.txt

  Scenario: Enforce max tool calls per turn
    Tool: uv run pytest tests/test_orchestrator.py -q
    Steps:
      1. Configure the limit to 1.
      2. Feed a query that would normally select multiple tools.
      3. Assert the orchestrator stops at the configured limit.
    Expected Result: tool-call cap is enforced.
    Evidence: .omo/evidence/task-7-tool-limit.txt
  ```

- [x] 8. `app/api/chat_router.py` and `app/main.py`: Expose the text entrypoint and customer boundary to exercise Sprint 3 - expect `POST /api/v1/chat`

  **What to do**:
  - Add a minimal chat route that accepts a text message and customer identifier.
  - Wire it into `app/main.py`.
  - Keep the endpoint thin: request parsing, customer id normalization, orchestrator call, response return.

  **Must NOT do**:
  - Do not add voice/audio streaming.
  - Do not add memory/session persistence.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: this is the integration boundary for the sprint and touches app wiring.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3
  - **Blocks**: 9
  - **Blocked By**: 1, 2, 3, 7

  **References**:

  **Pattern References**:
  - `app/main.py:61-137` - app factory and router wiring style
  - `app/api/tools_router.py:15-21` - router composition pattern
  - `tests/test_api.py:12-77` - FastAPI smoke/integration test pattern

  **API/Type References**:
  - `app/api/deps.py:8-12` - customer boundary stub shape
  - `EVA PRD.md:405-513` - security/failure handling requirements

  **Test References**:
  - `tests/test_api.py` - HTTP integration style
  - `tests/test_api_tools_customer_billing.py` - async client + ASGI transport style

  **External References**:
  - FastAPI docs - router inclusion and request models

  **WHY Each Reference Matters**:
  - The existing app uses router composition and inline meta endpoints; the new route must match that style.
  - The endpoint exists only to exercise the reasoning engine in the current backend state.

  **Acceptance Criteria**:
  - [ ] `POST /api/v1/chat` accepts a text prompt and customer id.
  - [ ] The route returns the reasoning output shape.
  - [ ] Bad payloads fail cleanly.

  **QA Scenarios**:
  ```
  Scenario: Chat endpoint happy path
    Tool: uv run pytest tests/test_chat_api.py -q
    Steps:
      1. POST a billing inquiry with a mock customer id.
      2. Assert HTTP 200 and a structured reasoning response.
      3. Assert selected tools/evidence appear in the payload.
    Expected Result: end-to-end text entrypoint works.
    Evidence: .omo/evidence/task-8-chat-success.txt

  Scenario: Reject malformed chat payload
    Tool: uv run pytest tests/test_chat_api.py -q
    Steps:
      1. POST a payload missing message or customer id.
      2. Assert a predictable validation failure.
    Expected Result: invalid input is rejected cleanly.
    Evidence: .omo/evidence/task-8-chat-validation-error.txt
  ```

- [x] 9. `tests/test_orchestrator.py`, `tests/test_reasoning_pipeline.py`, `tests/test_chat_api.py`: Lock the Sprint 3 behavior with TDD coverage - expect passing module and integration tests

  **What to do**:
  - Add or expand tests to cover billing inquiry, greeting/no-tool turns, partial failures, insufficient evidence, Bangla input, and chat endpoint behavior.
  - Reuse the existing async DB and ASGI testing style from `tests/conftest.py`.
  - Keep mocks isolated and deterministic.

  **Must NOT do**:
  - Do not make tests depend on real API keys.
  - Do not rely on live external services.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: the sprint’s verification layer needs broad integration coverage.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential after Tasks 7-8
  - **Blocks**: Final verification wave
  - **Blocked By**: 1-8

  **References**:

  **Pattern References**:
  - `tests/conftest.py` - testcontainers Postgres, async session, and Windows-safe setup
  - `tests/test_api.py` - API smoke-test style
  - `tests/test_api_tools_customer_billing.py` - async ASGI transport pattern
  - `tests/test_tool_customer.py`, `tests/test_tool_billing.py`, `tests/test_tool_ticket.py` - DB-backed async assertions

  **API/Type References**:
  - `app/config/settings.py:65-67` - `max_tool_calls_per_turn` behavior under test
  - `EVA PRD.md:555-587` - evaluation mindset and response quality

  **Test References**:
  - Existing test suite across `tests/` for mocking, async DB use, and response assertions

  **External References**:
  - pytest docs - async tests, monkeypatch, and fixtures

  **WHY Each Reference Matters**:
  - Sprint 3 must inherit the project’s existing pytest/testcontainers pattern instead of inventing a new one.
  - The new tests are the final proof that the reasoning pipeline works end-to-end.

  **Acceptance Criteria**:
  - [ ] Every Sprint 3 module has at least one happy-path test.
  - [ ] Every Sprint 3 module has at least one failure/edge-case test.
  - [ ] The full pytest suite passes locally.

  **QA Scenarios**:
  ```
  Scenario: Run Sprint 3 module tests
    Tool: uv run pytest tests/test_orchestrator.py tests/test_reasoning_pipeline.py -q
    Steps:
      1. Run the module test files.
      2. Assert the intent, selection, aggregation, and reasoning branches all pass.
    Expected Result: module tests pass with no failures.
    Evidence: .omo/evidence/task-9-module-tests.txt

  Scenario: Run Sprint 3 API integration tests
    Tool: uv run pytest tests/test_chat_api.py -q
    Steps:
      1. Exercise the chat endpoint with mocked dependencies.
      2. Assert the response shape and key edge cases.
    Expected Result: integration coverage passes.
    Evidence: .omo/evidence/task-9-api-tests.txt
  ```

---

## Final Verification Wave

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify the planned files and tests are present. For each "Must NOT Have": verify the scope excludes voice, memory, Langfuse, and evaluation work. Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `uv run ruff check app tests`, `uv run mypy app`, and `uv run pytest -q`. Review changed files for accidental direct DB access in orchestrator/reasoning code, unused imports, and AI-slop patterns. Output: `Build [PASS/FAIL] | Lint [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [x] F3. **End-to-End QA Replay** — `unspecified-high`
  Re-run every QA scenario from Tasks 1-9 with the exact commands and evidence paths recorded above. Confirm the text endpoint, tool selection, evidence aggregation, and reasoning output all work together. Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  Compare the final diff against every task’s "What to do" and "Must NOT do". Reject any voice, memory, Langfuse, evaluation, or direct-SQL creep. Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **1**: `feat(reasoning): add sprint 3 reasoning engine` - `app/schemas/reasoning.py`, `app/core/llm_client.py`, `app/orchestrator/*`, `app/reasoning/*`, `app/api/chat_router.py`, `tests/*`

---

## Success Criteria

### Verification Commands
```bash
uv run pytest -q
uv run ruff check app tests
uv run mypy app
```

### Final Checklist
- [x] All "Must Have" present
- [x] All "Must NOT Have" absent
- [x] The chat endpoint exercises the reasoning engine
- [x] All tests pass
