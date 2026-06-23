# Draft: Reimplement Auth with BetterAuth

## Requirements (confirmed)
- Replace Authlib with BetterAuth completely
- Google OAuth authentication
- Custom JWT issuance (24h TTL, stateless)
- Sync new users to `customers` table
- Block unauthenticated access at frontend router and backend API layers
- Keep `MOCK_AUTH_ENABLED` logic intact for test compatibility
- `customer_id` extracted from JWT, not client payloads
- Frontend uses TanStack Router (NOT Next.js) — cannot use Next.js auth patterns
- Stateless logout only (client-side JWT deletion)
- Everything else stays the same

## Research Findings

### BetterAuth Overview
- **BetterAuth** is a TypeScript/Node.js auth framework (28.7K GitHub stars), NOT a Python library
- Website: better-auth.com | GitHub: better-auth/better-auth
- It runs as its own server (Express, Hono, Next.js, etc.) and handles:
  - Google OAuth via `socialProviders.google`
  - User/session/account management in its own database tables
  - JWT issuance via the `jwt` plugin with JWKS endpoint at `/api/auth/jwks`
  - JWTs signed with EdDSA (Ed25519), verifiable via public keys

### FastAPI Integration
- **`fastapi-betterauth`** (PyPI, v0.2.6) — community package (7 stars) that verifies BetterAuth JWTs via JWKS
- Alternative: Manual JWKS verification using `pyjwt` + `cryptography`
- Flow: Frontend signs in via BetterAuth → gets JWT → sends to FastAPI as Bearer token → `BetterAuth` dependency fetches public keys from JWKS endpoint → verifies token
- Pattern from docs: `BetterAuth("http://localhost:3000")` dependency on FastAPI

### Architecture Impact
- **NEW: BetterAuth Node.js server** — must run as a separate process (TypeScript)
- Three services now: Frontend (Vite :3000) + BetterAuth server (Node.js :3001) + FastAPI (:8000)
- BetterAuth needs its own database tables: `user`, `session`, `account`, `verification`, `jwks`
- Google OAuth callback goes to BetterAuth, not FastAPI
- CORS configs need updating to allow frontend→BetterAuth and BetterAuth→FastAPI

### Key Gotchas
1. `redirect_uri_mismatch` — MUST set `BETTER_AUTH_URL` explicitly for correct Google OAuth redirects
2. `cookieCache` bugs — disable `cookieCache: { enabled: false }` to avoid silent logouts
3. JWT plugin is for service-to-service tokens, not session replacement
4. BetterAuth has NO native Python client — only JWT bridge or cookie-sharing patterns

## Technical Decisions
- PENDING: Where to host the BetterAuth Node.js server?
- PENDING: Database strategy for BetterAuth tables?
- PENDING: JWT verification approach (community package vs manual)?
- PENDING: Development workflow for 3 services?

## Open Questions
- See questions below

## Scope Boundaries
- INCLUDE: BetterAuth server (Node.js), Google OAuth, JWT via JWKS, customer sync, frontend auth guards, all existing auth files rewritten
- EXCLUDE: No other backend changes, no extra OAuth providers, no server-side session
