# Learnings — EVA Sprint 3

Session started 2026-06-10

## 2026-06-10 — LLM Client abstraction created (pp/core/llm_client.py)

### Key design decisions

- **Injection via client parameter**: LLMClient.__init__(client=...) accepts a pre-configured google.genai.Client for DI. This is cleaner than subclassing and lets tests pass a MagicMock directly.
- **LLMClientError as single error type**: Wraps SDK APIError, ClientError, ServerError so consumers never import google.genai.errors.
- **Async methods**: Both generate() and generate_structured() are async, matching the SDK's client.aio.models.generate_content().
- **Structured output via native SDK**: generate_structured() sets esponse_mime_type="application/json" and esponse_schema=<model>. The SDK populates esponse.parsed automatically.
- **Fallback JSON parsing**: If esponse.parsed is None (rare), the client falls back to esponse_schema.model_validate_json(response.text).
- **Both dict and model instances from .parsed**: The SDK may return a plain dict in some versions — the client normalises via esponse_schema.model_validate(parsed).

### Settings consumed
- settings.google_api_key — empty string check enforced at construction time
- settings.gemini_model — defaults to "gemini-2.0-flash"

### Test patterns
- Mock the SDK client at the client.aio.models.generate_content level using AsyncMock
- Return fake GenerateContentResponse objects with .text / .parsed / .prompt_feedback attributes
- LLMClient(api_key="sk-test", client=fake) bypasses settings entirely
- SDK APIError(code=..., response_json=...) is constructable with code (int) and esponse_json (dict) — NOT equest= / esponse= kwargs

### Files created
- pp/core/llm_client.py (125 LOC)
- 	ests/test_llm_client.py (210 LOC, 13 tests)

### Gotchas
- google.genai.errors.APIError.__init__(code, response_json, response=None) — equest kwarg is NOT accepted
- GenerateContentResponse.text is a @property, not a model field — it concatenates text parts from the first candidate
- GenerateContentResponse.parsed is None when esponse_schema is not set, or when the response is blocked
- Empty google_api_key defaults to "" in settings — the client must check this explicitly

## 2026-06-10 — Intent Analyzer created (app/orchestrator/intent_analyzer.py)

### Key design decisions

- **Internal response model**: `_IntentLLMResponse` (private Pydantic model) is used as the `response_schema` for `generate_structured()`. The public method normalises this into `IntentAnalysisResult` from schemas/reasoning.py.
- **System prompt drives classification**: All intent rules (billing_inquiry, support_ticket, knowledge_query, account_query, analytics_query, greeting, other) live in `_SYSTEM_PROMPT` — the LLM is instructed with exact tool name strings and source name strings per intent.
- **Multilingual support**: System prompt explicitly instructs handling of Bangla (Bengali), English, and code-switched input. Bangla billing/greeting examples are baked into the prompt.
- **Greeting edge case**: Greetings yield empty `candidate_tools` and `candidate_sources` with confidence >= 0.9, so downstream orchestration can short-circuit.
- **customer_context passing**: Optional `dict` is serialised into the LLM prompt for contextual intent classification. When absent, only the message is sent.

### Test patterns established

- `_fake_sdk_client()` + `_parsed_response(model)` helper mimics `GenerateContentResponse` with `.parsed` set to an `_IntentLLMResponse` instance.
- `@pytest.fixture` provides the `analyzer` (with mocked `LLMClient`) — each test overrides `mock_sdk.aio.models.generate_content.return_value`.
- Both English and Bangla variants tested for billing_inquiry and greeting intents.
- `LLMClientError` propagation tested via `side_effect` on the SDK mock.

### Files created
- app/orchestrator/intent_analyzer.py (165 LOC)
- tests/test_intent_analyzer.py (297 LOC, 14 tests)
- .omo/evidence/task-3-intent-billing.txt
- .omo/evidence/task-3-intent-greeting.txt

## 2026-06-10 — Tool Selector created (app/orchestrator/tool_selector.py)

### Key design decisions

- **Deterministic policy, no LLM**: The `ToolSelector` is a pure rule-based policy. It does not make any LLM calls — it orders, validates, deduplicates, and caps candidate tools from the intent analyzer.
- **Two-tier cap**: Intent-specific max tools (e.g., billing=4, support_ticket=3) are stricter than the global `max_tool_calls_per_turn` (default 6). The effective cap is `min(global_cap, intent_cap)`.
- **Low-confidence safety**: When `confidence < 0.3`, the cap is further tightened to at most 1 tool.
- **Priority ordering via position map**: `_apply_ordering()` creates a `{tool_name: index}` dict from the intent's ordered list, filters candidate_tools to only those in the list, then sorts by index — O(n) filtering and O(n log n) sorting.
- **Dedup via `dict.fromkeys()`**: Preserves insertion order while removing duplicates in one pass.
- **Greeting/other short-circuit**: Checked before any other logic so these intents always return empty tool lists, regardless of what the LLM put in `candidate_tools`.

### Settings consumed
- `settings.max_tool_calls_per_turn` — global cap (default 6), overridable via constructor `max_calls` parameter

### Test patterns
- Pure unit tests — no mocks, no fixtures. The selector has no external dependencies.
- `@pytest.mark.asyncio` on every test (selector's `select()` is async to match orchestrator interface).
- Parameterised test via `@pytest.mark.parametrize` covers all 7 intent types in one function.
- Intent-specific ordering tests verify tools are correctly reordered and capped.
- Unknown tool names tested by including `"non_existent_tool"` in candidate_tools.
- Determinism tested by calling `select()` twice with the same input and asserting identical output.

### Files created
- app/orchestrator/tool_selector.py (150 LOC)
- tests/test_tool_selector.py (320 LOC, 30 tests)
- .omo/evidence/task-4-tool-selection-billing.txt
- .omo/evidence/task-4-tool-selection-empty.txt

### Gotchas
- The `select()` method is `async def` even though it never awaits — this matches the orchestrator interface pattern and avoids accidental sync/async mismatch.
- `customer_context` defaults to `{}` internally when `None` is passed, but the constructor parameter type is `dict | None` so callers can pass `None` without type errors.
- Tool name strings must exactly match the function names in `app/tools/*/functions.py` (e.g., `get_billing_history`, not `get_billing_history_endpoint`).

## 2026-06-10 — Evidence Aggregator created (app/orchestrator/evidence_aggregator.py)

### Key design decisions

- **Stateless converter pattern**: `EvidenceAggregator` takes no constructor arguments — it's a pure function object. The `aggregate()` method accepts `dict[str, ToolResult]` and returns `EvidencePackage`.
- **Builder registry dispatch**: Each known tool name has a dedicated builder function registered in `_TOOL_BUILDERS`. Unknown tool names fall through to a generic builder that sets `source=tool_name`, `content=str(data)`, and `metadata={}`.
- **List vs. scalar branching**: The aggregator uses `isinstance(data, list)` to decide whether to iterate (one `EvidenceItem` per element) or wrap as a single-element list. Empty lists and `None` data (even with `success=True`) are silently skipped — they do **not** count as failures.
- **Partial-failure semantics**: Failed tools (`success=False`) are collected in `failed_tools` but do not block successful tools. `data=None` with `success=True` is skipped without adding to `failed_tools`.
- **Content varies by tool type**: Knowledge tool items (`search_documentation`, `search_policies`) use `data.content` (raw text) as the EvidenceItem content, while all other tools use `data.model_dump_json()`.

### Test patterns

- Real Pydantic model instances (CustomerProfile, BillingRecordModel, etc.) constructed via fixtures — no mocks.
- `ToolResult.ok(data)` / `ToolResult.fail(error)` factory methods used throughout.
- `json.loads(item.content)` to verify JSON-string content contains expected fields for non-knowledge tools.
- Knowledge tool content verified as raw text strings (not JSON).
- `_assert_evidence_item()` helper extracts common source/tool_name/metadata checks.
- Partial-failure test covers all edge cases in one test: successful lists, successful singles, empty list (skipped), None data (skipped), and two different failures.

### Files created
- app/orchestrator/evidence_aggregator.py (280 LOC)
- tests/test_evidence_aggregator.py (370 LOC, 21 tests)
- .omo/evidence/task-5-evidence-package.txt
- .omo/evidence/task-5-partial-failure.txt

## 2026-06-10 — Reasoning Pipeline created (app/reasoning/pipeline.py)

### Key design decisions

- **Two-path architecture**: The `reason()` method branches on evidence availability. Empty evidence → deterministic fallback (no LLM call). Evidence present → LLM-based reasoning via `generate_structured()`.
- **Hallucination prevention**: The insufficient-evidence path is hard-coded and never calls the LLM. Even with evidence, the system prompt explicitly forbids using external knowledge: "You must ONLY use the evidence provided below. Do NOT use any external knowledge or training data to answer."
- **Private internal model**: `_ReasoningLLMResponse` is used as the `response_schema` for `generate_structured()`, then normalised into the public `ReasoningOutput` schema.
- **Greeting/other short-circuit**: Empty evidence with greeting or other intent gets a friendly deterministic response (with name personalisation from customer_context), not an LLM call.
- **Reasoning type validation**: Invalid reasoning_type from the LLM falls back to `evidence_corroboration` via `_VALID_REASONING_TYPES`.
- **Confidence clamping**: Raw LLM confidence is clamped to `[0.0, 1.0]` via `max(0.0, min(1.0, ...))`.
- **Failed tools in prompt**: Evidence package's `failed_tools` list is included in the LLM prompt so the model knows what information might be missing.
- **Evidence indexing**: Multiple evidence items are numbered `[Item 1]`, `[Item 2]`, etc. in the prompt for clear reference.

### Settings consumed
- None (only LLMClient which reads settings internally)

### Test patterns
- Same mock patterns as intent_analyzer: `_fake_sdk_client()`, `_parsed_response(model)`, `_make_llm_response()` helpers.
- `@pytest.fixture` provides `pipeline`, `empty_package`, `single_evidence_package`, `multi_evidence_package` fixtures.
- `mock_sdk.aio.models.generate_content.assert_not_awaited()` to verify the insufficient-evidence path skips the LLM.
- Evidence items created via `_make_evidence_item()` fixture helper with source/tool_name/content.
- Multi-evidence package includes failed tools to test `failed_tools` in prompt.
- Confidence clamping tested via out-of-range values (2.5 and -0.5).
- Invalid reasoning_type tested to verify fallback.
- All 4 valid reasoning types tested via loop.

### Files created
- app/reasoning/pipeline.py (260 LOC)
- tests/test_reasoning_pipeline.py (470 LOC, 25 tests)
- .omo/evidence/task-6-reasoning-success.txt
- .omo/evidence/task-6-insufficient-evidence.txt

## 2026-06-10 — Chat Router created (app/api/chat_router.py)

### Key design decisions

- **Router prefix matches tools_router pattern**: `APIRouter(prefix="/api/v1/chat", tags=["Chat"])` — identical style to `tools_router.py`.
- **Existing ChatRequest/ChatResponse schemas reused**: `app/schemas/reasoning.py` already defined both models, so no new schemas were needed — the router just imports and wires them.
- **Thin endpoint**: The `POST /` handler only parses the request, constructs `OrchestratorService`, calls `process_turn()`, and returns the result. No business logic lives in the router.
- **customer_context merging**: The mock `current_user` dict from `get_current_user()` is merged with `request.customer_id` so the orchestrator uses the caller-supplied id while keeping the mock name/email for context.
- **LLMClient() constructed with no args**: Reads settings internally — matches the production pattern established in Sprint 3.
- **get_db_session dependency**: Passed as `AsyncSession` to the orchestrator's `session` parameter.

### Files created
- app/api/chat_router.py (38 LOC)

### Files modified
- app/main.py — added `from app.api.chat_router import chat_router` import and `app.include_router(chat_router)` wiring

### Test patterns
- Verified clean import: `uv run python -c "from app.api.chat_router import chat_router; print('OK')"`
- Original 17 Sprint-1 tests pass unchanged.
- All 193 Sprint-3 unit tests (excluding pre-existing failures in API integration tests) pass.

## 2026-06-10 — Orchestrator Service created (app/orchestrator/service.py)

### Key design decisions

- **Composition over inheritance**: `OrchestratorService` takes 4 injectable sub-components (analyzer, selector, aggregator, pipeline) plus `LLMClient` and `AsyncSession` as required constructor params. All injectable params are keyword-only with default `None` — when `None`, the service constructs the real implementation internally.
- **`_TOOL_FUNCTIONS` registry**: A `dict[str, Callable]` maps tool name strings to async functions. Initialised with all 8 tool functions from the 5 tool modules. Can be monkeypatched in tests without affecting other tests.
- **`_execute_tools()` internal method**: Takes `selected_tools: list[str]`, `max_tool_calls: int`, and `context: dict`. Returns `dict[str, ToolResult]`. Iterates over selected tools in order, enforces the cap, catches `DomainException` → `ToolResult.fail()` and generic `Exception` → `ToolResult.fail("Unexpected error: ...")`.
- **Tool limit enforcement at orchestrator level**: Even if `ToolSelector` returns more tools than `max_tool_calls`, the orchestrator enforces the cap inside `_execute_tools()`. Surplus tools get `ToolResult.fail("Tool call limit exceeded")` without ever being invoked.
- **`_build_tool_kwargs()` helper**: Converts `customer_id` (string) to `uuid.UUID` via `uuid.UUID(customer_id)`, extracts `ticket_id` and `query` from context. Returns a kwargs dict that each tool function can destructure via `**kwargs` or explicit params.
- **Single `LLMClient` instance**: The orchestrator creates one `LLMClient` (or receives one) and passes it to both `IntentAnalyzer` and `ReasoningPipeline`. This avoids redundant connection overhead.

### Settings consumed
- `settings.max_tool_calls_per_turn` — read by `ToolSelector` internally; the orchestrator trusts `ToolSelectionPlan.max_tool_calls`

### Test patterns

- **Monkeypatch `_TOOL_FUNCTIONS`**: Tests replace individual functions with `AsyncMock` to isolate tool execution behaviour.
- **Mock sub-components**: All 4 sub-components are mocked via `AsyncMock(spec=...)` with `return_value` set to real Pydantic model instances. Spy assertions (`assert_awaited_once`) verify the orchestrator calls each component correctly.
- **Real `LLMClient`**: Tests pass `LLMClient(api_key="sk-test", client=mock_sdk)` with a mocked SDK to avoid real API calls.
- **Pydantic model return values from tool mocks**: Critical — tool mocks must return model instances (e.g., `BillingRecordModel`, `TicketModel`), not `dict`, because the evidence aggregator calls `.model_dump_json()` and accesses attributes like `.id`, `.status`.
- **Helper factories**: `_make_billing_record()`, `_make_ticket()`, `_make_knowledge_result()`, `_make_customer_profile()` fixtures create model instances with sensible defaults, with optional overrides for specific fields.
- **`side_effect` list for dual LLM calls**: Tests that need both intent analysis and reasoning mock the SDK client with `side_effect=[intent_response, reasoning_response]` for the two sequential `generate_content` calls.
- **Customer ID constant**: `_TEST_CUSTOMER_ID = "550e8400-e29b-41d4-a716-446655440000"` used throughout to avoid magic strings.

### Files created
- app/orchestrator/service.py (220 LOC)
- tests/test_orchestrator.py (872 LOC, 15 tests)
- .omo/evidence/task-7-turn-success.txt
- .omo/evidence/task-7-tool-limit.txt

### Gotchas
- Tool functions return Pydantic model instances, not dicts — the evidence aggregator accesses `.model_dump_json()` and attribute access like `.id`. Mock return values MUST be model instances.
- The orchestrator creates a single `LLMClient` shared by analyzer + pipeline. Tests need `side_effect` list for two sequential `generate_content` calls (intent → reasoning).
- Greeting/other: only 1 SDK call (intent analysis). Pipeline handles greeting deterministically without LLM.
- `ToolSelector` is deterministic (no LLM). `EvidenceAggregator` is stateless.
- `DomainException` in tool execution → `ToolResult.fail()`. Generic `Exception` → `ToolResult.fail()` with `"Unexpected error: {e}"`.
- `UUID` conversion via `uuid.UUID(customer_id)` — tests use a valid UUID string constant.
- Knowledge tools (`search_documentation`, `search_policies`) receive `query=message` (customer's original text).
- `get_ticket_status` receives `ticket_id=None` — gracefully fails with `DomainException` caught → `ToolResult.fail()`.
- The `_execute_tools()` iteration preserves tool order from `ToolSelectionPlan` and stops exactly at `max_tool_calls`.

## 2026-06-10 — Chat Endpoint wired (app/api/chat_router.py + tests/test_chat_api.py)

### Key design decisions

- **Thin endpoint, no business logic**: The `chat()` handler only parses the request, merges customer context, constructs `OrchestratorService`, calls `process_turn()`, and returns the result. Zero business logic in the router.
- **Dependency override pattern for tests**: API tests use `app.dependency_overrides` to replace `get_db_session` and `get_current_user` with mocks. The patched session and user dict are injected into the orchestrator without needing a real database.
- **Orchestrator-level mocking in API tests**: Since the orchestrator is already thoroughly unit-tested (15 tests in `test_orchestrator.py`), API tests mock the entire `OrchestratorService` class at the `app.api.chat_router` namespace. This avoids the complexity of mocking all internal sub-components and SDK.
- **Dual patch for constructor**: Both `LLMClient` and `OrchestratorService` must be patched in `app.api.chat_router` because the endpoint constructs `LLMClient()` (which fails without a real API key) before constructing the orchestrator.
- **Validation-first error handling**: Missing `message` or `customer_id` returns 422 without ever reaching the orchestrator — FastAPI/Pydantic validation intercepts at the routing layer.

### Test patterns

- **`@patch` decorator on class**: All 7 test methods use `@patch("app.api.chat_router.LLMClient")` and `@patch("app.api.chat_router.OrchestratorService")` to mock both dependencies that crash without real credentials.
- **`_make_fake_chat_response()` helper**: Constructs a fake `ChatResponse` with configurable response text, tool calls, and evidence presence.
- **Validation tests need no mocks**: Missing-field tests (422) don't need any patches — FastAPI validation fires before the endpoint function is called.
- **`dependency_overrides.clear()` in teardown**: The `app_with_overrides` fixture clears overrides after each test to prevent cross-test contamination.

### Files created
- tests/test_chat_api.py (237 LOC, 7 tests)
- .omo/evidence/task-8-chat-success.txt
- .omo/evidence/task-8-chat-validation-error.txt

### Gotchas
- The `TestClient` loads the app eagerly, but patches applied via `@patch` run before the fixture setup. Order: `@patch` decorator → fixture setup → test body.
- `LLMClient()` is called before `OrchestratorService()` in the endpoint, so both must be patched even when testing orchestrator behavior.
- `get_settings().google_api_key` defaults to `""` — `LLMClient()` raises if no key is set, which is why the mock is needed even when the orchestrator is also mocked.

## 2026-06-10 — Orchestrator tests updated (tests/test_orchestrator.py)

### Tests added
- `TestUnknownToolName.test_unknown_tool_returns_failure`: Verifies that when a tool name not present in `_TOOL_FUNCTIONS` is selected, the orchestrator produces `ToolResult.fail("Unknown tool: ...")` instead of crashing. The tool name appears in `tool_calls_made` and `evidence.failed_tools`.

### Key learnings
- The real `ToolSelector._apply_ordering()` filters out unknown tool names via `KNOWN_TOOLS` and `_INTENT_TOOL_ORDER` before they reach the execution loop. To test the unknown-tool path in the orchestrator, you must **inject a mock selector** that returns a plan with the unknown tool name — otherwise the selector silently drops it.
- The `_TOOL_FUNCTIONS` dict is module-level in `app.orchestrator.service` and can be monkeypatched via `monkeypatch.setitem(orchestrator_service._TOOL_FUNCTIONS, "tool_name", mock)` or `@patch.dict("app.orchestrator.service._TOOL_FUNCTIONS", ...)`.
- `orchestrator_service._TOOL_FUNCTIONS` is imported as a module reference (`from app.orchestrator import service as orchestrator_service`) so `monkeypatch.setitem` on the module's attribute works correctly.
- The orchestrator enforces the tool cap from `plan.max_tool_calls` (not its own constructor `max_tool_calls`). Slicing `plan.selected_tools[:plan.max_tool_calls]` is the enforcement point.

### Test patterns established
- **Unknown tool test**: Inject `AsyncMock(spec=ToolSelector)` returning a `ToolSelectionPlan` with the unknown tool name. No `monkeypatch` needed on `_TOOL_FUNCTIONS` — test verifies the orchestrator's graceful handling when the tool function is missing.
- The existing 15 tests use a real `LLMClient` with a mocked SDK client, while 1 test (`TestSubComponentCalls`) uses fully injected mocked sub-components.
- `@patch.dict` approach (not shown in existing tests) can also replace `_TOOL_FUNCTIONS` wholesale with `clear=True`.

### Files modified
- tests/test_orchestrator.py — added TestUnknownToolName class (1 test, 16 total)
