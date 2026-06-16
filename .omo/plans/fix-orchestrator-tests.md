# Orchestrator Test Suite Fixes

## TL;DR

> **Quick Summary**: Fix the 13 failing tests in the test suite caused by recent orchestrator and pipeline updates, and resolve outstanding `ruff` linting errors.
> 
> **Deliverables**: 
> - Updated `test_chat_api.py` with proper memory mocks
> - Updated `test_orchestrator.py` & `test_reasoning_pipeline.py` with correct greeting assertions
> - Fixed factory context manager mock in `test_orchestrator.py`
> - Cleaned up `test_seed.py` state handling
> - Resolved `B008` (Depends in defaults) and `E501` (line length) lint errors
> 
> **Estimated Effort**: Quick
> **Parallel Execution**: YES - 1 wave
> **Critical Path**: Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → F1-F4

---

## Context

### Original Request
The test suite is failing after the Bounded Adaptive Reasoning, Parallel DB Session, and Langfuse updates. `uv run pytest` reports 13 failures and `uv run ruff check` reports pre-existing linting warnings.

### Interview Summary
**Research Findings**:
- `test_chat_api.py` failures are caused by calling an un-mocked `DbConversationStore` with a mocked session.
- Greeting test failures are caused by an outdated assertion (`"Hello"` instead of `"Good day"`).
- `test_orchestrator.py` session isolation test fails because the factory side-effect doesn't properly mock the async context manager (`__aenter__` / `__aexit__`).
- `test_seed.py` fails due to leftover DB state.
- `ruff` issues (`B008`) exist across API routers because `Depends()` is used in default arguments.

---

## Work Objectives

### Core Objective
Achieve a 100% pass rate on `uv run pytest` and zero errors on `uv run ruff check`.

### Concrete Deliverables
- `tests/test_chat_api.py`
- `tests/test_orchestrator.py`
- `tests/test_reasoning_pipeline.py`
- `tests/test_seed.py`
- `app/api/` (linting fixes)

### Definition of Done
- [ ] `uv run pytest` passes cleanly (ignoring Docker unavailability skips).
- [ ] `uv run ruff check app tests` returns zero errors.

### Must Have
- Test coverage must not be reduced; assertions must be updated accurately, not removed.

### Must NOT Have (Guardrails)
- Do not modify `app/orchestrator/service.py` core logic.

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES
- **Automated tests**: YES
- **Framework**: pytest
- **Agent-Executed QA**: The final wave will run `pytest` and `ruff` to ensure absolute compliance.

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately - Test Suite Fixes):
├── 1. Fix test_chat_api.py DB memory mocks [quick]
├── 2. Update greeting text assertions [quick]
├── 3. Fix session factory context manager mocks [quick]
├── 4. Fix test_seed.py state [quick]
└── 5. Resolve Ruff B008 and E501 errors [quick]

Wave FINAL (Review):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)
```

---

## TODOs

- [ ] 1. Fix `test_chat_api.py` DbConversationStore Mocks

  **What to do**:
  - Add an `autouse=True` fixture in `tests/test_chat_api.py` that patches `app.api.chat_router._memory`.
  - The patched memory should have `format_prompt_context` returning `AsyncMock(return_value="")` and `add_turn` returning `AsyncMock()`.

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single fixture addition in one file.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: None
  - **Blocked By**: None

  **References**:
  - `tests/test_chat_api.py` - Needs the patch.

  **QA Scenarios**:
  ```
  Scenario: Pytest passes for chat API
    Tool: interactive_bash
    Preconditions: None
    Steps:
      1. run `uv run pytest tests/test_chat_api.py`
    Expected Result: All tests pass (or skip cleanly if no docker), 0 failures.
    Evidence: .omo/evidence/task-1-chat-api-tests.txt
  ```

- [ ] 2. Update Greeting Text Assertions

  **What to do**:
  - In `tests/test_orchestrator.py` (`test_greeting_skips_tools`, `test_other_intent_also_skips_tools`) and `tests/test_reasoning_pipeline.py` (all `TestEmptyEvidenceGreeting` methods), change assertions expecting `"Hello"` or `"Hello!"` to expect `"Good day"`.

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple string replacements.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: None
  - **Blocked By**: None

  **QA Scenarios**:
  ```
  Scenario: Pytest passes for greeting tests
    Tool: interactive_bash
    Preconditions: None
    Steps:
      1. run `uv run pytest tests/test_orchestrator.py tests/test_reasoning_pipeline.py`
    Expected Result: 0 failures related to greeting assertions.
    Evidence: .omo/evidence/task-2-greeting-tests.txt
  ```

- [ ] 3. Fix Session Factory Context Manager Mock

  **What to do**:
  - In `tests/test_orchestrator.py` (`test_each_tool_gets_separate_session`), the `mock_session_factory.return_value.side_effect` must return an object whose `__aenter__` is an `AsyncMock` returning the session, not a standard `MagicMock`.
  - Alternatively, patch the tool implementations to ensure they are actually awaiting the session factory correctly.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Async context manager mocking in Python can be tricky.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: None
  - **Blocked By**: None

  **QA Scenarios**:
  ```
  Scenario: Pytest passes for session isolation
    Tool: interactive_bash
    Preconditions: None
    Steps:
      1. run `uv run pytest tests/test_orchestrator.py::TestParallelSessionIsolation`
    Expected Result: 0 failures.
    Evidence: .omo/evidence/task-3-isolation-test.txt
  ```

- [ ] 4. Fix test_seed.py State

  **What to do**:
  - In `tests/test_seed.py` (`test_seed_first_run_populates_tables`), modify the `_seed` call to use `Namespace(reset=True)` instead of `False`, or clear the `customers` table before running the test so it doesn't fail if the DB already contains rows.

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: One line fix.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: None
  - **Blocked By**: None

  **QA Scenarios**:
  ```
  Scenario: Seed test passes
    Tool: interactive_bash
    Preconditions: Docker is available for DB tests.
    Steps:
      1. run `uv run pytest tests/test_seed.py`
    Expected Result: Test passes cleanly.
    Evidence: .omo/evidence/task-4-seed-test.txt
  ```

- [ ] 5. Resolve Ruff B008 and E501 Errors

  **What to do**:
  - In `app/api/chat_router.py`, `app/api/tools_*.py`, remove `Depends(...)` from default arguments or suppress the rule if standard FastAPI practice dictates keeping them. FastAPI conventionally ignores B008 for `Depends`. Adding `# ruff: noqa: B008` to the top of those files is an acceptable fix.
  - In `tests/*.py`, wrap or format lines exceeding 100 characters (E501).

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Formatting and linting adjustments.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: None
  - **Blocked By**: None

  **QA Scenarios**:
  ```
  Scenario: Ruff passes cleanly
    Tool: interactive_bash
    Preconditions: None
    Steps:
      1. run `uv run ruff check app tests`
    Expected Result: No errors found.
    Evidence: .omo/evidence/task-5-ruff.txt
  ```

---

## Final Verification Wave

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Verify all 5 test fixes were applied without altering core business logic.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `uv run ruff check app tests`. Verify no new warnings are introduced.
  Output: `Build [PASS/FAIL] | Lint [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high`
  Run `uv run pytest`. Verify all tests either pass or gracefully skip.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  Verify diff logs. Ensure `app/orchestrator/service.py` was not structurally modified during this pass.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Success Criteria

### Verification Commands
```bash
uv run pytest
uv run ruff check app tests
```

### Final Checklist
- [ ] All tests pass
- [ ] Ruff linting passes
