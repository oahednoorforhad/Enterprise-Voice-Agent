# Docker Deployment Design — Enterprise Voice Agent

**Date:** 2026-06-24  
**Status:** Approved (v2 — post code-review)  
**Author:** Oahed Noor Forhad

---

## Overview

Containerize the full Enterprise Voice Agent stack (FastAPI backend + React/Vite frontend + PostgreSQL) for production deployment on a DigitalOcean Droplet, with HTTPS via Nginx + Let's Encrypt (Certbot), automated CI/CD via GitHub Actions, and error monitoring via Sentry.

---

## Architecture

```
Internet
    │
    ▼
Nginx (:80 → redirect to :443)
Nginx (:443, SSL via Let's Encrypt)
    │
    ├── /api/*          → backend:8000   (HTTP + WebSocket)
    └── /*              → frontend:80    (static HTML/JS/CSS)

Internal Docker network (unexposed):
    backend:8000  ←→  postgres:5432
    certbot  →  writes certs to shared volume  →  nginx reads them
```

### Services

| Container | Image | Role |
|---|---|---|
| `nginx` | nginx:alpine | Reverse proxy, SSL termination |
| `certbot` | certbot/certbot | Obtains & renews Let's Encrypt certs |
| `backend` | ghcr.io/\<your-github-username\>/eva-backend | FastAPI + Uvicorn, runs migrations on start |
| `frontend` | ghcr.io/\<your-github-username\>/eva-frontend | Nginx serving built React static files |
| `postgres` | pgvector/pgvector:0.8.0-pg16 | Primary database + vector store (pinned, matches dev) |

**Only `nginx` exposes ports 80 and 443 to the internet. All other containers communicate over an internal Docker network.**

---

## Files to Create

```
project root/
├── Dockerfile                          # Backend image (Python 3.12, FastAPI)
├── frontend/
│   └── Dockerfile                      # Frontend image (multi-stage: Node → Nginx)
├── docker/
│   ├── docker-compose.prod.yml         # All 5 production services
│   ├── nginx/
│   │   ├── nginx.conf                  # Main Nginx config
│   │   └── conf.d/
│   │       ├── app.http.conf           # HTTP → HTTPS redirect + ACME challenge
│   │       └── app.https.conf          # HTTPS reverse proxy (env-substituted domain)
│   └── postgres/
│       └── init.sql                    # Already exists — no change
├── scripts/
│   ├── init-letsencrypt.sh             # One-time: bootstrap first SSL cert
│   ├── backup-db.sh                    # Nightly pg_dump backup script
│   └── deploy.sh                       # Pull images + restart containers on Droplet
├── .env.prod.example                   # Template for production secrets
└── .github/
    └── workflows/
        └── deploy.yml                  # GitHub Actions CI/CD pipeline
```

---

## Backend Dockerfile

- Base: `python:3.12-slim`
- Install `uv`, copy `uv.lock` + `pyproject.toml`, run `uv sync --frozen` for reproducible installs
- Entrypoint: run `alembic upgrade head` then start `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- No `--reload` in production
- Runs as non-root user for security
- Healthcheck: `curl -f http://localhost:8000/health || exit 1` (interval: 10s, retries: 5)

## Frontend Dockerfile

Multi-stage build:
1. **Stage 1 (build):** `node:20-alpine` — install deps, `npm run build` → outputs to `/app/dist`
2. **Stage 2 (serve):** `nginx:alpine` — copy `/app/dist` into Nginx web root, serve static files on :80
- `VITE_API_URL` injected at build time via Docker `--build-arg VITE_API_URL=https://<domain>` so the frontend knows the production API base URL. Vite bakes this into the built JS bundle at compile time (not runtime).

---

## Nginx Configuration

### HTTP (:80)
- Serve Let's Encrypt ACME challenge files from a shared volume (required for cert issuance)
- Redirect all other traffic to HTTPS

### HTTPS (:443)
- SSL certificates from `/etc/letsencrypt/live/<domain>/` — domain substituted at container startup via `envsubst`, reading `$DOMAIN` from environment
- Proxy `/api/*` → `http://backend:8000` with headers:
  - `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`
  - `Upgrade` + `Connection: upgrade` for WebSocket support (voice stream at `/api/v1/voice/stream`)
- All other requests → `http://frontend:80`
- Nginx reloads every 12h via cron to pick up renewed certificates

---

## Certbot (Let's Encrypt)

- Domain: `eva.<DROPLET_IP>.sslip.io` (free wildcard DNS via sslip.io — more reliable than nip.io)
- Challenge type: HTTP-01 (Certbot serves a file, Let's Encrypt verifies via port 80)
- `init-letsencrypt.sh` runs once on first deploy to obtain the initial certificate
- Certbot container runs `certbot renew` on a schedule; Nginx picks up renewed certs on its 12h reload
- Certificates stored in a named Docker volume shared between `certbot` and `nginx`

---

## Database Migrations

Auto-run on backend startup:

```dockerfile
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

- If migration fails, the backend exits immediately — deployment fails visibly rather than silently
- Alembic tracks applied migrations in `alembic_version` table — safe to run on every deploy (no-op if up to date)
- Future schema changes: create a new migration with `alembic revision --autogenerate`, commit it, redeploy

---

## Healthchecks & Service Dependencies

```yaml
postgres:
  healthcheck:
    test: pg_isready -U eva -d eva   # same pattern as dev compose
    interval: 5s
    timeout: 3s
    retries: 5
    start_period: 10s

backend:
  depends_on:
    postgres:
      condition: service_healthy     # backend waits for DB before starting
  healthcheck:
    test: curl -f http://localhost:8000/health || exit 1
    interval: 10s
    timeout: 5s
    retries: 5
    start_period: 15s               # alembic migration needs time

nginx:
  depends_on:
    backend:
      condition: service_healthy
    frontend:
      condition: service_started
```

This prevents the race condition where `alembic upgrade head` runs before PostgreSQL is accepting connections.

---

## Resource Limits

On a 2GB Droplet, a memory leak in any container can OOM the host. Each service gets a `mem_limit`:

| Service | `mem_limit` |
|---|---|
| postgres | 512m |
| backend | 512m |
| frontend | 128m |
| nginx | 128m |
| certbot | 64m |

Total ceiling: ~1.3GB — leaves headroom for the OS and Docker daemon on a 2GB Droplet.

---

## Database Backup

Nightly `pg_dump` via `scripts/backup-db.sh`, run as a cron job on the Droplet:

```bash
# /etc/cron.d/eva-backup (added during server setup)
0 2 * * * root /opt/eva/scripts/backup-db.sh >> /var/log/eva-backup.log 2>&1
```

`backup-db.sh` dumps to `/var/backups/eva/eva-YYYY-MM-DD.sql`, keeps the last 7 days, and logs success/failure. No external storage needed initially — backups live on the Droplet's disk. If the Droplet's data volume is mounted separately (DigitalOcean Volumes), backups survive even if the Droplet is rebuilt.

---

## CI/CD Pipeline (GitHub Actions)

**Trigger:** Push to `main` branch

**Steps:**
1. Checkout code
2. Log in to GitHub Container Registry (GHCR) — free, no DockerHub needed
3. Build and push `ghcr.io/<user>/eva-backend:latest`
4. Build and push `ghcr.io/<user>/eva-frontend:latest` (with `VITE_API_URL` build arg)
5. SSH into Droplet:
   - `docker compose -f docker/docker-compose.prod.yml pull`
   - `docker compose -f docker/docker-compose.prod.yml up -d`
   - `docker image prune -f` ← removes only dangling (untagged) images, not running containers or their images

**Total deploy time:** ~3–5 minutes. Droplet stays running; only containers restart.

### GitHub Secrets (set once in repo settings)

| Secret | Purpose |
|---|---|
| `DROPLET_HOST` | Droplet IP address |
| `DROPLET_SSH_KEY` | Private SSH key for Droplet access |
| `GOOGLE_API_KEY` | Gemini API key |
| `DATABASE_URL` | PostgreSQL connection string on Droplet |
| `LANGFUSE_PUBLIC_KEY` | Observability (optional) |
| `LANGFUSE_SECRET_KEY` | Observability (optional) |
| `DOMAIN` | e.g. `eva.1.2.3.4.sslip.io` |
| `SENTRY_DSN` | Sentry project DSN for error monitoring |
| `VITE_SENTRY_DSN` | Sentry DSN for frontend error monitoring |

---

## Monitoring — Sentry

**Choice: Sentry over Grafana.**

Grafana requires a Prometheus metrics pipeline (extra containers, exporters, config) — overkill for a solo deployment at this stage. Sentry integrates directly into FastAPI and React with ~10 lines of code each, free tier covers 5K errors/month, and gives you stack traces, request context, and release tracking out of the box.

You already have **Langfuse** for LLM observability (prompt traces, tool calls, reasoning steps). Sentry covers the **application layer** (unhandled exceptions, API errors, frontend crashes). These two together give full observability without Grafana complexity.

### Backend integration

```python
# app/main.py
import sentry_sdk
sentry_sdk.init(dsn=settings.SENTRY_DSN, environment=settings.ENVIRONMENT)
```

### Frontend integration

```ts
// frontend/src/main.tsx
import * as Sentry from "@sentry/react"
Sentry.init({ dsn: import.meta.env.VITE_SENTRY_DSN, environment: "production" })
```

Sentry SDK packages to add:
- Backend: `sentry-sdk[fastapi]`
- Frontend: `@sentry/react`

Free tier: 5K errors/month, 10K performance transactions/month, 1 user — sufficient for early production.

---

## One-Time Server Setup (done once, never repeated)

1. Create a DigitalOcean Droplet (Ubuntu 24.04, 2GB RAM — ~$12/month)
2. SSH in, install Docker + Docker Compose plugin
3. Clone repo onto Droplet
4. Create `.env.prod` from `.env.prod.example`, fill in real values
5. Run `scripts/init-letsencrypt.sh` — obtains first SSL certificate
6. Run `docker compose -f docker/docker-compose.prod.yml up -d`
7. Add cron job for nightly DB backup (`scripts/backup-db.sh`)
8. Add GitHub Secrets to repo
9. All future deploys happen automatically via `git push`

---

## Environment Variables

### Production `.env.prod`

| Variable | Required | Notes |
|---|---|---|
| `ENVIRONMENT` | No | Set to `production` |
| `DATABASE_URL` | Yes | `postgresql+asyncpg://eva:eva@postgres:5432/eva` (internal Docker hostname) |
| `GOOGLE_API_KEY` | Yes | Gemini API key |
| `DOMAIN` | Yes | e.g. `eva.1.2.3.4.sslip.io` |
| `POSTGRES_PASSWORD` | Yes | Strong password for DB |
| `CORS_ORIGINS` | Yes | `["https://eva.1.2.3.4.sslip.io"]` |
| `MOCK_AUTH_ENABLED` | No | Must be `false` in production |
| `SENTRY_DSN` | No | Sentry project DSN (recommended) |
| `LANGFUSE_PUBLIC_KEY` | No | Optional LLM observability |
| `LANGFUSE_SECRET_KEY` | No | Optional LLM observability |

**Note:** `DATABASE_URL` uses `postgres` (Docker service name) as hostname, not `localhost`.

---

## Droplet Size Recommendation

| RAM | Cost | Suitability |
|---|---|---|
| 1 GB | ~$6/mo | Too tight with resource limits applied |
| 2 GB | ~$12/mo | Comfortable — recommended |
| 4 GB | ~$24/mo | Headroom for scale |

With $200 in DigitalOcean credits, a 2GB Droplet runs for ~16 months free.

---

## WebSocket Handling

The voice stream endpoint (`/api/v1/voice/stream`) uses WebSocket. Nginx must proxy it correctly:

```nginx
location /api/v1/voice/stream {
    proxy_pass http://backend:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 3600s;
}
```

The frontend's `VoiceInterface.tsx` must connect to `wss://` (not `ws://`) in production — the connection goes through Nginx's TLS termination.

---

## Security Decisions

- All containers run on an internal Docker network; only Nginx is internet-facing
- Backend runs as non-root user in container
- `MOCK_AUTH_ENABLED=false` enforced in production env
- Secrets managed via GitHub Secrets (CI/CD) and `.env.prod` on Droplet (never committed)
- `.env.prod` added to `.gitignore`
- Resource limits prevent any single container from OOMing the host

---

## Reviewer Feedback Resolution

| Item | Decision |
|---|---|
| `system prune` → `image prune` | Fixed — `docker image prune -f` only removes dangling images |
| Healthchecks + `depends_on` | Added — reuses `pg_isready` pattern from dev compose |
| Pin pgvector tag | Fixed — `0.8.0-pg16` matches dev compose |
| DB backup strategy | Added — nightly `pg_dump` cron, 7-day retention |
| nip.io → sslip.io | Fixed — more reliable DNS service |
| Resource limits | Added — `mem_limit` per service |
| uv.lock missing | Not actioned — `uv.lock` already exists and is committed |
| Monitoring | Added — Sentry (not Grafana; Grafana requires Prometheus pipeline, overkill here) |
