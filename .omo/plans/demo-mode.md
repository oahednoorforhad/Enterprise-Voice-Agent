# Marketing Demo Mode

## TL;DR
> **Quick Summary**: Transform EVA into a marketing asset by building a public landing page and a "Demo Mode" using the Clone Pattern, allowing prospects to inject realistic persona data into isolated accounts to test the AI safely.
> 
> **Deliverables**:
> - Public SaaS landing page at `/`
> - Persona Selector screen at `/scenarios` (5 distinct personas)
> - `POST /api/v1/demo/apply-scenario` to clone JSON templates
> - `is_demo` safety flag to protect real customer data
> 
> **Estimated Effort**: Large
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Task 1 (DB) → Task 3 (Clone Endpoint) → Task 7 (Persona UI)

---

## Context

### Original Request
User wants to expose EVA to LinkedIn for marketing. Instead of prospects dropping into an empty dashboard, they should be able to choose from 5 demo situations (e.g., Billing Issue) and see their account populated with realistic fake data.

### Interview Summary
**Key Discussions**:
- Avoid the "Empty Dashboard" problem with guided storytelling (5 personas).
- Avoid the "Shared Account Chaos" problem using the **Clone Pattern**: users get their own isolated copy of the data.
- **Safe Clone**: We must protect real users from accidentally wiping their data if they hit the persona selector.

### Metis Review
**Identified Gaps** (addressed):
- **Destructive Cloning**: Resolved by adding an `is_demo` flag to `Customer`. Only demo accounts can be wiped/cloned.
- **Content Scope**: User decided to build all 5 personas upfront.
- **Admin Access**: Added a secret admin API to flip accounts from demo to real.

---

## Work Objectives

### Core Objective
Transform EVA into a viral marketing asset by building a public landing page and a "Demo Mode" that lets prospects clone realistic persona data (tickets, billing, etc.) into their isolated accounts to safely test the AI.

### Concrete Deliverables
- DB migration for `is_demo` and `active_scenario` on `customers`.
- `data/scenarios/*.json` containing 5 realistic personas.
- `POST /api/v1/demo/apply-scenario` endpoint.
- `POST /api/v1/admin/set-real-user` endpoint.
- `frontend/app/routes/index.tsx` as a public landing page.
- `frontend/app/routes/scenarios.tsx` Persona Selector.
- Demo Mode UI indicator badge.

### Definition of Done
- [ ] Unauthenticated users see a public landing page at `/`.
- [ ] New Google signups are routed to `/scenarios`.
- [ ] Selecting a scenario populates the dashboard with fake data and redirects the user.
- [ ] The EVA AI correctly reads the cloned data.

### Must Have
- The clone endpoint MUST reject requests if `is_demo=False`.
- The clone endpoint MUST `DELETE` existing child records (tickets, billing) before inserting the cloned template to prevent duplication.
- `OverviewPage` MUST be moved to `/overview`.

### Must NOT Have (Guardrails)
- Do NOT alter the core LLM reasoning pipeline or voice tools. They already read from the DB, so they will work automatically.
- Do NOT build a full marketing site; the landing page is a Minimal CTA only.

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES
- **Automated tests**: YES (tests-after for new endpoints)
- **Agent-Executed QA**: ALWAYS. Playwright for the new UI flow, `curl` for the backend endpoints.

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.omo/evidence/task-{N}-{scenario-slug}.{ext}`.

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately - Backend & Data):
├── Task 1: DB Migration (is_demo & active_scenario) [quick]
├── Task 2: JSON Seed Data (5 Personas) [artistry]
├── Task 3: Backend Clone Endpoint [deep]
└── Task 4: Admin Endpoint [quick]

Wave 2 (After Wave 1 - Frontend & Routing):
├── Task 5: Move OverviewPage & Protect Routes [visual-engineering]
├── Task 6: Public Landing Page [visual-engineering]
├── Task 7: Update Auth Callback [quick]
└── Task 8: Persona Selector Screen [visual-engineering]

Wave 3 (After Wave 2 - Integration):
├── Task 9: Demo Mode UI Indicators [visual-engineering]
└── Task 10: Pytest & Playwright Integration Tests [unspecified-high]

Wave FINAL (After ALL tasks):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)
```

### Dependency Matrix
- **1**: -
- **2**: -
- **3**: 1, 2
- **4**: 1
- **5**: -
- **6**: 5
- **7**: 5, 8
- **8**: 3
- **9**: 8
- **10**: 3, 8

---

## TODOs

- [x] 1. DB Migration (is_demo & active_scenario)

  **What to do**:
  - Add `is_demo: Mapped[bool] = mapped_column(default=True, server_default=text("true"))` to `Customer` in `app/db/models.py`.
  - Add `active_scenario: Mapped[str | None] = mapped_column(String(50), nullable=True)` to `Customer`.
  - Update `auth_router.py` to set `is_demo=True` when creating a new customer.
  - Run `uv run alembic revision --autogenerate -m "add demo fields"`.

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Standard SQLAlchemy/Alembic update.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: 3, 4
  - **Blocked By**: None

  **References**:
  - `app/db/models.py`
  - `app/api/auth_router.py`

  **Acceptance Criteria**:
  - [ ] Alembic migration succeeds.
  - [ ] New Google OAuth signups default to `is_demo=True`.

  **QA Scenarios**:
  ```
  Scenario: Check DB migration
    Tool: interactive_bash
    Preconditions: DB running
    Steps:
      1. run `uv run alembic upgrade head`
      2. check columns exist in `customers` table
    Expected Result: Columns exist.
    Evidence: .omo/evidence/task-1-db.txt
  ```

- [x] 2. JSON Seed Data (5 Personas)

  **What to do**:
  - Create `data/scenarios/` directory.
  - Create `billing_dispute.json`, `technical_bug.json`, `happy_upgrade.json`, `churn_risk.json`, `new_onboarding.json`.
  - Each JSON should represent data to insert into `subscriptions`, `billing_records`, `support_tickets`, `usage_analytics`, `crm_notes`. Use UUID placeholders or array formats that the endpoint can map to the active `customer_id`.

  **Recommended Agent Profile**:
  - **Category**: `artistry`
    - Reason: Requires creating realistic, high-quality mock data for 5 different situations.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: 3
  - **Blocked By**: None

  **References**:
  - `scripts/seed_single_user.py` - use this as a reference for realistic data fields.

  **Acceptance Criteria**:
  - [ ] 5 JSON files exist with valid schema matching the DB tables.

  **QA Scenarios**:
  ```
  Scenario: Validate JSON structures
    Tool: interactive_bash
    Preconditions: Files created
    Steps:
      1. load each json in python and verify keys match SQLAlchemy models
    Expected Result: No key errors.
    Evidence: .omo/evidence/task-2-json.txt
  ```

- [x] 3. Backend Clone Endpoint

  **What to do**:
  - Create `app/api/demo_router.py`.
  - Endpoint `POST /api/v1/demo/apply-scenario`:
    - Depends on `get_current_user`.
    - Accepts `{ "scenario_id": "billing_dispute" }`.
    - Fetches Customer. If `is_demo=False`, raise 403.
    - DELETES all child records for this customer (or relies on SQLAlchemy cascades if deleting/recreating, but safer to `delete().where(customer_id=...)` for subscriptions, tickets, etc.).
    - Reads the corresponding JSON from `data/scenarios/`.
    - Inserts the new records, tying them to `customer_id`.
    - Updates `Customer.active_scenario = scenario_id`.
  - Register router in `main.py`.

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Complex DB transaction with cascading deletes and multiple table inserts.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: 8, 10
  - **Blocked By**: 1, 2

  **References**:
  - `app/db/models.py`
  - `app/api/deps.py`

  **Acceptance Criteria**:
  - [ ] Endpoint successfully wipes and replaces data.
  - [ ] Returns 403 for non-demo users.

  **QA Scenarios**:
  ```
  Scenario: Apply Scenario Clone
    Tool: Bash (curl)
    Preconditions: User exists with is_demo=True and a valid JWT
    Steps:
      1. curl POST /api/v1/demo/apply-scenario with scenario_id
    Expected Result: HTTP 200, data populated
    Evidence: .omo/evidence/task-3-clone.txt
  ```

- [x] 4. Admin Endpoint

  **What to do**:
  - Add `POST /api/v1/admin/set-real-user` in a new `admin_router.py`.
  - Takes `{ "email": "admin@example.com" }`.
  - Secures via a secret token from settings (e.g. `settings.admin_secret_key`).
  - Sets `Customer.is_demo = False` for the given email.
  - Register in `main.py`.

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple endpoint.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: None
  - **Blocked By**: 1

  **References**:
  - `app/config/settings.py`

  **Acceptance Criteria**:
  - [ ] Endpoint updates `is_demo`.

  **QA Scenarios**:
  ```
  Scenario: Admin flip
    Tool: Bash (curl)
    Preconditions: Server running, admin secret set
    Steps:
      1. curl POST /api/v1/admin/set-real-user
    Expected Result: HTTP 200
    Evidence: .omo/evidence/task-4-admin.txt
  ```

- [x] 5. Move OverviewPage & Protect Routes

  **What to do**:
  - In `frontend/app/router.tsx`, change the path for `OverviewPage` from `/` to `/overview`.
  - Update `Sidebar.tsx` to point to `/overview` instead of `/`.
  - Ensure `/overview`, `/dashboard`, `/chat`, `/voice`, `/analytics`, `/knowledge`, `/scenarios` all have `beforeLoad: requireAuth`.

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Route restructuring.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: 6, 7
  - **Blocked By**: None

  **References**:
  - `frontend/app/router.tsx`

  **Acceptance Criteria**:
  - [ ] Old dashboard is now at `/overview`.

  **QA Scenarios**:
  ```
  Scenario: Overview redirect
    Tool: playwright
    Preconditions: Valid JWT
    Steps:
      1. Navigate to /overview
    Expected Result: Page loads successfully
    Evidence: .omo/evidence/task-5-overview.png
  ```

- [x] 6. Public Landing Page

  **What to do**:
  - Create a new `frontend/app/routes/index.tsx` (or update existing if Task 5 renamed the file).
  - Build a Minimal CTA page: Hero headline ("Enterprise AI Support Agent"), subheadline, and a "Sign in with Google" button pointing to `http://localhost:8000/api/v1/auth/login/google`.
  - Do NOT require auth for this route.
  - Remove or integrate `login.tsx` (if users can just use the button on the landing page).

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Landing page UI.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: None
  - **Blocked By**: 5

  **References**:
  - `frontend/app/routes/index.tsx`

  **Acceptance Criteria**:
  - [ ] `/` is accessible without login and has Google login button.

  **QA Scenarios**:
  ```
  Scenario: Public Landing Page
    Tool: playwright
    Preconditions: Logged out
    Steps:
      1. Navigate to /
    Expected Result: Renders landing page without redirecting
    Evidence: .omo/evidence/task-6-landing.png
  ```

- [x] 7. Update Auth Callback

  **What to do**:
  - Update `frontend/app/routes/auth_callback.tsx` (or similar).
  - After saving the JWT, make an API call to fetch the user's profile (`api.customerProfile`).
  - If `profile.active_scenario` is null/empty AND `profile.is_demo` is true, redirect to `/scenarios`.
  - Otherwise, redirect to `/overview`.

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Routing logic update.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: None
  - **Blocked By**: 5, 8

  **References**:
  - `frontend/app/routes/auth_callback.tsx`

  **Acceptance Criteria**:
  - [ ] New users are forced to `/scenarios`.

  **QA Scenarios**:
  ```
  Scenario: Callback routing
    Tool: playwright
    Preconditions: Mocked JWT for new user
    Steps:
      1. Hit callback URL
    Expected Result: Redirects to /scenarios
    Evidence: .omo/evidence/task-7-callback.txt
  ```

- [x] 8. Persona Selector Screen

  **What to do**:
  - Create `frontend/app/routes/scenarios.tsx`.
  - UI: A clean grid/list of the 5 personas with descriptions.
  - When clicked: Call `POST /api/v1/demo/apply-scenario`.
  - On success, redirect to `/overview`.

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: UI creation for selection grid.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: 7, 9, 10
  - **Blocked By**: 3

  **References**:
  - `frontend/app/routes/scenarios.tsx`

  **Acceptance Criteria**:
  - [ ] Persona selector renders and successfully triggers clone.

  **QA Scenarios**:
  ```
  Scenario: Persona Selection
    Tool: playwright
    Preconditions: Logged in, on /scenarios
    Steps:
      1. Click a persona card
    Expected Result: API call made, redirects to /overview
    Evidence: .omo/evidence/task-8-selector.png
  ```

- [x] 9. Demo Mode UI Indicators

  **What to do**:
  - Update `Sidebar.tsx` or `__root.tsx`.
  - If `user.is_demo` is true, show a prominent badge: "DEMO MODE: [Scenario Name]".
  - Add a "Switch Persona" button that links back to `/scenarios`.

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: UI state representation.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3
  - **Blocks**: None
  - **Blocked By**: 8

  **References**:
  - `frontend/app/components/Sidebar.tsx`

  **Acceptance Criteria**:
  - [ ] Demo badge visible for demo users.

  **QA Scenarios**:
  ```
  Scenario: Demo badge visibility
    Tool: playwright
    Preconditions: Logged in as demo user
    Steps:
      1. View dashboard
    Expected Result: Badge is visible
    Evidence: .omo/evidence/task-9-badge.png
  ```

- [x] 10. Pytest & Playwright Integration Tests

  **What to do**:
  - Add pytest for `/api/v1/demo/apply-scenario` to verify data wiping/cloning.
  - Add playwright test to run through Landing Page -> Login -> Persona Select -> Dashboard.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Integration testing.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3
  - **Blocks**: None
  - **Blocked By**: 3, 8

  **References**:
  - `tests/`

  **Acceptance Criteria**:
  - [ ] All tests pass.

  **QA Scenarios**:
  ```
  Scenario: Run tests
    Tool: interactive_bash
    Preconditions: Server running
    Steps:
      1. uv run pytest
    Expected Result: Tests pass
    Evidence: .omo/evidence/task-10-tests.txt
  ```

---

## Final Verification Wave

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists. For each "Must NOT Have": verify absence. Check evidence files.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `tsc --noEmit` + linter + `bun test`. Review all changed files.
  Output: `Build [PASS/FAIL] | Lint [PASS/FAIL] | Tests [N pass/N fail] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Execute EVERY QA scenario from EVERY task.
  Output: `Scenarios [N/N pass] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  Verify 1:1 diff against spec. Detect cross-task contamination.
  Output: `Tasks [N/N compliant] | VERDICT`

---

## Commit Strategy
- **1**: `feat: add demo mode database columns and seeds`
- **2**: `feat: implement backend clone endpoint`
- **3**: `feat: add persona selector and landing page`

## Success Criteria
### Verification Commands
```bash
uv run pytest
npm run typecheck
```
### Final Checklist
- [x] All "Must Have" present
- [x] All "Must NOT Have" absent
- [x] All tests pass
