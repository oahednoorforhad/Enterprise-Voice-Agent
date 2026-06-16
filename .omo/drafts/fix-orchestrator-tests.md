# Draft: Orchestrator Test Suite Fixes

## Requirements (confirmed)
- Fix all 13 failing tests in the test suite resulting from the Bounded Adaptive Reasoning and Langfuse updates.
- Achieve 100% pass rate on `uv run pytest`.
- Resolve any residual `ruff` linting errors in the test files (e.g., `B008`, `E501`).

## Technical Decisions
- **Chat API Mocking**: Inject an `autouse=True` fixture in `test_chat_api.py` to mock `app.api.chat_router._memory` with AsyncMocks for `format_prompt_context` and `add_turn`.
- **Greeting Assertions**: Update all tests asserting `"Hello"` to assert `"Good day"` to match the current pipeline logic.
- **Factory Mocking**: Fix the `session_factory` mock in `TestParallelSessionIsolation` to properly yield an `AsyncMock` context manager.
- **Seed Test**: Pass `--reset` explicitly in `test_seed.py` or clear the `Customer` table beforehand.

## Scope Boundaries
- INCLUDE: Modifying test files `test_chat_api.py`, `test_orchestrator.py`, `test_reasoning_pipeline.py`, `test_seed.py`. Fixing `ruff` errors in API routers and tests.
- EXCLUDE: Altering core implementation logic in `app/orchestrator/service.py` (it is working as intended).