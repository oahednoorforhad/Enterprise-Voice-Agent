# Google OAuth Integration Plan

## TL;DR
> **Quick Summary**: Implement Google OAuth using Authlib on FastAPI, issue custom JWTs, sync new users to the `customers` database table via email matching, and enforce authentication barriers across TanStack Router and FastAPI endpoints.
> 
> **Deliverables**: 
> - Google OAuth login & callback routes (`/api/v1/auth/*`)
> - Custom JWT issuance and validation middleware
> - Alembic migration for `google_id` on `customers`
> - TanStack Router auth barrier and login UI
> - Updated WebSocket and HTTP clients to use JWT
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Task 2 (DB) → Task 4 (Backend Auth) → Task 7 (Frontend Auth)

---

## Context

### Original Request
Build a robust, flawless end-to-end plan to execute Google OAuth authentication, issue custom JWTs, secure all routes (barrier layer), sync new users to DB, and handle secure logout.

### Interview Summary
**Key Discussions**:
- Avoid Next.js specific auth libraries (Auth.js/NextAuth) as the frontend is TanStack Router.
- Authlib on FastAPI is the chosen backend solution.
- WebSocket auth will use query parameters (`?token=<jwt>`).
- DB Sync: Match users by email. If not found, create new Customer. Update `google_id`.

**Metis Review Gaps Addressed**:
- Defined linking strategy (email matching).
- Defined logout strategy (stateless client-side deletion, 24h JWT TTL).
- Decided on `localStorage` for JWT storage for simplicity and WebSocket compatibility.
- Kept `MOCK_AUTH_ENABLED` for existing tests.
- Replaced client-trusted `customer_id` with server-trusted `customer_id` extracted from JWT.

---

## Work Objectives

### Core Objective
Enable Google single sign-on for the EVA application by issuing custom JWTs via FastAPI/Authlib, syncing users to the `customers` table, and blocking unauthenticated access at both the frontend router and backend API layers.

### Concrete Deliverables
- `alembic` migration adding `google_id`
- `app/api/auth_router.py` with Google OAuth endpoints
- `app/core/security.py` with JWT logic
- `app/api/deps.py` with real JWT verification
- `frontend/app/routes/login.tsx` UI
- `frontend/app/router.tsx` protected route logic
- Updated `voice_router.py` WebSocket auth

### Definition of Done
- [ ] Unauthenticated access to `/chat` redirects to `/login`.
- [ ] Google login creates/updates a user in the DB.
- [ ] Subsequent API and WebSocket calls successfully authenticate via the issued JWT.

### Must Have
- JWT validation must reject expired or invalid tokens.
- `customer_id` must be extracted from the JWT, not trusted from client payloads.
- Existing tests must still pass using `MOCK_AUTH_ENABLED=true`.

### Must NOT Have (Guardrails)
- Must NOT modify existing `Customer` columns (additive only).
- Must NOT implement 2FA or RBAC.
- Must NOT implement server-side token revocation (stateless logout only).

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES (pytest, testcontainers)
- **Automated tests**: YES (Tests-after for new auth endpoints)
- **Agent-Executed QA**: ALWAYS. Playwright for UI flow, `curl` for backend endpoints.

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.omo/evidence/task-{N}-{scenario-slug}.{ext}`.

---

## Execution Strategy

### Parallel Execution Waves

Wave 1 (Start Immediately - Foundation):
├── Task 1: Add dependencies & config [quick]
├── Task 2: Database Migration (google_id) [quick]
└── Task 3: JWT Security Utilities [quick]

Wave 2 (After Wave 1 - Auth Logic):
├── Task 4: Google OAuth Router (`login` & `callback`) [unspecified-high]
└── Task 5: Backend Auth Guards & WS Update [unspecified-high]

Wave 3 (After Wave 2 - Frontend Integration):
├── Task 6: Frontend Auth State & API Client Update [visual-engineering]
├── Task 7: Login UI & TanStack Router Barrier [visual-engineering]
└── Task 8: Test Suite Updates [unspecified-high]

Wave FINAL (After ALL tasks):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)

---

## TODOs

---

- [x] 1. Add dependencies & config

  **What to do**:
  - Add `authlib` and `PyJWT` to `pyproject.toml` dependencies.
  - Update `app/config/settings.py` to include `google_client_id`, `google_client_secret`, `google_redirect_uri`, `jwt_secret`, and `jwt_algorithm` (default "HS256").
  - Update `.env.example` with the new environment variables and set `MOCK_AUTH_ENABLED=false` as the documented default for new setups.

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple config and dependency updates.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: 4, 5
  - **Blocked By**: None

  **References**:
  - `pyproject.toml` - dependency list
  - `app/config/settings.py` - Pydantic settings
  - `.env.example` - env template

  **Acceptance Criteria**:
  - [ ] `uv sync` installs `authlib` and `PyJWT` successfully.
  - [ ] App starts without validation errors when new env vars are provided.

  **QA Scenarios**:
  ```
  Scenario: App starts with new config
    Tool: interactive_bash
    Preconditions: Add dummy keys to .env
    Steps:
      1. run `uv run python -c "from app.config import get_settings; print(get_settings().jwt_algorithm)"`
    Expected Result: Output is "HS256"
    Evidence: .omo/evidence/task-1-config-check.txt
  ```

- [x] 2. Database Migration (google_id)

  **What to do**:
  - Add `google_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)` to the `Customer` model in `app/db/models.py`.
  - Ensure `email` has an explicit index if not already present (unique implies index but good to be explicit).
  - Generate an Alembic migration script using `uv run alembic revision --autogenerate -m "add google_id"`.

  **Must NOT do**:
  - Do NOT modify existing fields or alter existing records in a breaking way.

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Standard SQLAlchemy model update and Alembic generation.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: 4
  - **Blocked By**: None

  **References**:
  - `app/db/models.py` - Customer model
  - `alembic/env.py` - Migration environment

  **Acceptance Criteria**:
  - [ ] `uv run alembic upgrade head` succeeds.
  - [ ] DB schema contains `google_id` column.

  **QA Scenarios**:
  ```
  Scenario: Migration applies cleanly
    Tool: interactive_bash
    Preconditions: DB is running
    Steps:
      1. run `uv run alembic upgrade head`
      2. run `docker exec $(docker ps -q -f name=postgres) psql -U eva -d eva -c '\d customers'`
    Expected Result: Column google_id is present
    Evidence: .omo/evidence/task-2-db-schema.txt
  ```

- [x] 3. JWT Security Utilities

  **What to do**:
  - Create `app/core/security.py`.
  - Implement `create_access_token(data: dict, expires_delta: timedelta | None = None) -> str`. Default to 24 hours if no delta provided.
  - Implement `verify_token(token: str) -> dict`.
  - Use `settings.jwt_secret` and `settings.jwt_algorithm`.

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Isolated, pure-function utilities.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: 4, 5
  - **Blocked By**: None

  **References**:
  - `app/config/settings.py` - For secrets

  **Acceptance Criteria**:
  - [ ] Can create and verify a JWT successfully.
  - [ ] Verification fails for expired or tampered tokens.

  **QA Scenarios**:
  ```
  Scenario: JWT lifecycle
    Tool: interactive_bash
    Preconditions: None
    Steps:
      1. run a python script that creates a token, waits 1s, and verifies it.
      2. script attempts to verify an expired token and catches exception.
    Expected Result: Verification succeeds for valid token, fails for expired.
    Evidence: .omo/evidence/task-3-jwt-test.txt
  ```

- [x] 4. Google OAuth Router (`login` & `callback`)

  **What to do**:
  - Create `app/api/auth_router.py`.
  - Initialize Authlib `OAuth` with Google config.
  - Endpoint `GET /api/v1/auth/login/google`: return Authlib redirect.
  - Endpoint `GET /api/v1/auth/callback/google`: exchange code, extract `email` and `name`.
  - Look up Customer by email. If exists, update `google_id`. If not, create Customer (name, email, company=email domain, plan_tier="free", is_active=True, google_id).
  - Issue JWT with `sub=customer.id` and redirect to `http://localhost:3000/auth/callback?token=<jwt>`.
  - Register router in `main.py`.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Core auth logic, DB interaction, and external API integration.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: 6, 7
  - **Blocked By**: 1, 2, 3

  **References**:
  - `app/core/security.py` - JWT creation
  - `app/db/models.py` - Customer model

  **Acceptance Criteria**:
  - [ ] Login endpoint redirects to Google.

  **QA Scenarios**:
  ```
  Scenario: Login redirect
    Tool: interactive_bash
    Preconditions: Server running
    Steps:
      1. run `curl -v http://localhost:8000/api/v1/auth/login/google`
    Expected Result: HTTP 302 with location pointing to accounts.google.com
    Evidence: .omo/evidence/task-4-login-redirect.txt
  ```

- [x] 5. Backend Auth Guards & WS Update

  **What to do**:
  - Update `app/api/deps.py -> get_current_user()`: Read `Authorization: Bearer <token>`, verify via `security.verify_token()`. Extract `customer_id`.
  - Maintain `MOCK_AUTH_ENABLED` logic: if true, fallback to mock if no token.
  - Update all endpoints in `chat_router.py` to use `customer_id` from `get_current_user`, ignoring/overriding any client-supplied `customer_id`.
  - Update `app/api/voice_router.py`: Read `token` from query params. Verify JWT. Extract `customer_id`. Reject if invalid.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Securing endpoints and websocket connections.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: 8
  - **Blocked By**: 1, 3

  **References**:
  - `app/api/deps.py` - Dependency injection
  - `app/api/voice_router.py` - WebSocket

  **Acceptance Criteria**:
  - [ ] Unauthenticated requests to `/chat` fail (401) when mock is disabled.
  - [ ] WebSocket connections with invalid token fail.

  **QA Scenarios**:
  ```
  Scenario: Protected endpoint rejection
    Tool: interactive_bash
    Preconditions: Server running, MOCK_AUTH_ENABLED=false
    Steps:
      1. run `curl -X POST http://localhost:8000/api/v1/chat/ -H "Content-Type: application/json" -d '{"message":"hello"}'`
    Expected Result: HTTP 401 Unauthorized
    Evidence: .omo/evidence/task-5-unauthorized.txt
  ```

- [x] 6. Frontend Auth State & API Client Update

  **What to do**:
  - Update `frontend/app/lib/api-client.ts`: Inject `Authorization: Bearer <jwt>` from `localStorage.getItem('jwt')`.
  - Remove `customer_id` from client payloads where applicable.
  - Update `frontend/app/hooks/useVoiceSession.ts`: Fetch JWT from localStorage and append to WS URL instead of `"mock"`.

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Frontend state management and API integration.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3
  - **Blocks**: None
  - **Blocked By**: 4, 5

  **References**:
  - `frontend/app/lib/api-client.ts`
  - `frontend/app/hooks/useVoiceSession.ts`

  **Acceptance Criteria**:
  - [ ] API client attaches auth header.

  **QA Scenarios**:
  ```
  Scenario: Auth header injection
    Tool: playwright
    Preconditions: JWT in localStorage
    Steps:
      1. Trigger API call from frontend
      2. Intercept network request
    Expected Result: Authorization header is present
    Evidence: .omo/evidence/task-6-header.png
  ```

- [x] 7. Login UI & TanStack Router Barrier

  **What to do**:
  - Create `frontend/app/routes/login.tsx`: Simple UI with "Sign in with Google" button pointing to `http://localhost:8000/api/v1/auth/login/google`.
  - Create `frontend/app/routes/auth/callback.tsx`: Extracts `?token=` from URL, saves to `localStorage`, and redirects to `/`.
  - Implement Auth Barrier: Update `frontend/app/router.tsx` to check for JWT. Redirect unauthenticated users from protected routes (like `/chat`, `/voice`) to `/login`.
  - Add Logout button to sidebar: Clears localStorage and redirects to `/login`.

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: UI creation and routing logic.
  - **Skills**: [`playwright`]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3
  - **Blocks**: None
  - **Blocked By**: 4, 5

  **References**:
  - `frontend/app/router.tsx`

  **Acceptance Criteria**:
  - [ ] Unauthenticated users are redirected to `/login`.
  - [ ] Callback route successfully stores JWT.

  **QA Scenarios**:
  ```
  Scenario: Router barrier redirect
    Tool: playwright
    Preconditions: No JWT in localStorage
    Steps:
      1. Navigate to `/chat`
    Expected Result: URL changes to `/login`
    Evidence: .omo/evidence/task-7-barrier.png
  ```

- [x] 8. Test Suite Updates

  **What to do**:
  - Verify that existing backend tests continue to pass (they should, due to `MOCK_AUTH_ENABLED` logic or dependency overrides).
  - Add basic unit test for JWT creation/verification in `tests/test_auth_security.py`.
  - Add test for `get_current_user` dependency logic.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Test execution and verification.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3
  - **Blocks**: None
  - **Blocked By**: 5

  **References**:
  - `tests/`

  **Acceptance Criteria**:
  - [ ] `uv run pytest` passes 100%.

  **QA Scenarios**:
  ```
  Scenario: Test suite passes
    Tool: interactive_bash
    Preconditions: None
    Steps:
      1. run `uv run pytest`
    Expected Result: All tests pass
    Evidence: .omo/evidence/task-8-pytest.txt
  ```

---

## Final Verification Wave

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. Verify Must Haves and Must NOT Haves. Check evidence files.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `tsc --noEmit` + linter + `bun test`. Review all changed files.
  Output: `Build [PASS/FAIL] | Lint [PASS/FAIL] | Tests [N pass/N fail] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Execute EVERY QA scenario.
  Output: `Scenarios [N/N pass] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  Verify 1:1 diff against spec. Detect cross-task contamination.
  Output: `Tasks [N/N compliant] | VERDICT`

---

## Commit Strategy
- **1**: `feat(auth): add google oauth and jwt foundation`
- **2**: `feat(auth): implement frontend barriers and login ui`

## Success Criteria
### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass
