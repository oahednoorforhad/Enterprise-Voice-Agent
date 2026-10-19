# EVA Lightweight Deployment: Render + Neon

**Goal:** public, HTTPS, $0/month, no credit card, one deployable unit.
**Date:** 2026-10-19

## Architecture

```
Browser ──HTTPS/WSS──▶ Render free web service (1 Docker container)
                         FastAPI: /api/*, /api/v1/voice/stream (WS), SPA from /app/static
                              │
                              ▼
                       Neon Postgres (free, pgvector)
```

| Before (Droplet, 5 containers) | After |
|---|---|
| nginx + certbot | Render-managed TLS. Not used anymore. |
| frontend container | Built into the backend image (`Dockerfile` stage 1) |
| backend container | Render free web service (`render.yaml`) |
| postgres container | Neon free tier |
| SSH deploy workflow | Render auto-deploys on every push to `main` |

## Code changes (done)
- `Dockerfile`: multi-stage. It builds the React app with `VITE_API_URL=` (same origin) and copies it into `/app/static`. It no longer installs gcc, libpq-dev or curl. It listens on `$PORT`, which Render sets, and runs uvicorn with `--proxy-headers` so OAuth redirects use `https`.
- `app/main.py`: when `static/` exists, serves `/assets` and falls back to `index.html` for SPA routes. It is registered after all API routers. Local dev is unaffected because there is no `static/` dir there.
- `frontend/app/lib/api-client.ts` and `frontend/app/hooks/useVoiceSession.ts`: if `VITE_API_URL` is empty, use the same origin; WebSocket URL derived from `location.origin`. If it is unset, they still default to `localhost:8000`.
- `migrations/env.py`: converts `ssl=require` (asyncpg) to `sslmode=require` (psycopg), so one `DATABASE_URL` works for both the app and Alembic.
- `pyproject.toml`: moved `faker` and `pytest` from runtime dependencies to dev dependencies. `uv.lock` regenerated.
- `render.yaml`: Blueprint for the service. Secrets are marked `sync: false`, and `JWT_SECRET` and `ADMIN_SECRET_KEY` are auto-generated.

## Step 1: Neon (≈10 min)
1. Sign up at neon.tech (no card). Create a project in **AWS us-east-1**, close to Render's default Oregon region; Ohio/Virginia are fine too.
2. SQL editor: `CREATE EXTENSION IF NOT EXISTS vector;`
3. Copy the **direct** connection string (host has no `-pooler`). The pooler is PgBouncer in transaction mode, which breaks asyncpg prepared statements. Rewrite it as:
   ```
   postgresql+asyncpg://USER:PASS@ep-xxx.us-east-1.aws.neon.tech/neondb?ssl=require
   ```
4. Migrate and seed from your laptop (bash):
   ```bash
   export DATABASE_URL='postgresql+asyncpg://...?ssl=require'
   uv run alembic upgrade head
   uv run python -m scripts.seed_db
   uv run python -m scripts.seed_knowledge   # uses GOOGLE_API_KEY for embeddings
   ```

## Step 2: Render (≈10 min)
1. Commit and push these changes to GitHub.
2. render.com → sign in with GitHub → **New → Blueprint**, then pick this repo. It reads `render.yaml`.
3. Fill in the prompted secrets: `DATABASE_URL`, `GOOGLE_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `SENTRY_DSN` (blank is ok).
4. Wait for the first build (~5 min). Then:
   - `https://eva-xxxx.onrender.com/ready` should return `{"status":"ready","db":true,"vector":true}`
   - Open the site and test text chat, then voice.

While testing on `onrender.com`, temporarily set `CORS_ORIGINS`, `FRONTEND_URL` and `GOOGLE_REDIRECT_URI` to the `onrender.com` URL. Same-origin API calls don't need CORS, but OAuth redirects do need the right URL.

## Step 3: Domain `eva.oahed.live`
1. Render service → Settings → Custom Domains → add `eva.oahed.live`.
2. At your DNS provider, add `CNAME eva → eva-xxxx.onrender.com`. Render issues the TLS certificate automatically.
3. Google Cloud Console → OAuth client → authorized redirect URI `https://eva.oahed.live/api/v1/auth/callback/google`.
4. Set the three URL env vars back to `eva.oahed.live`, as they are in `render.yaml`.

## Step 4: Clean up old infrastructure
- **Disable or delete `.github/workflows/deploy.yml` now.** It still tries to SSH into the dead Droplet, so every push will fail CI.
- These files are now unused: `docker/docker-compose.prod.yml`, `docker/nginx/`, `frontend/Dockerfile`, `frontend/nginx.conf`, `scripts/init-letsencrypt.sh`, `scripts/deploy.sh`. Keep `docker/docker-compose.yml` for local dev.

## Free-tier limits you will feel

| Limit | Effect on EVA | Workaround |
|---|---|---|
| Spins down after 15 min with no traffic | First visit afterwards takes ~30–60 s | Open the site a minute before a demo, or ping `/health` every 10 min with a free cron service such as cron-job.org (still within 750 h/mo) |
| 512 MB RAM, 0.1 CPU | Startup and Alembic are slow-ish; voice is just audio relay, so it should hold | Upgrade to Starter ($7/mo) if audio stutters |
| 750 instance-hours/month | Enough for one always-on service | — |
| Neon compute scales to zero | ~0.5 s extra on the first query after idle | — |
| Render's free Postgres expires after 30 days | We don't use it, which is why Neon | — |

## Checklist
1. [ ] Neon: create project, enable `vector`, migrate, seed
2. [ ] Disable `deploy.yml`, commit, push
3. [ ] Render Blueprint, fill in secrets, first deploy is green
4. [ ] `/ready` returns green; chat and voice work on `onrender.com`
5. [ ] Custom domain, CNAME, OAuth redirect URI updated
