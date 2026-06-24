# Docker Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Containerize the Enterprise Voice Agent (FastAPI + React + PostgreSQL) for production deployment on a DigitalOcean Droplet with HTTPS, automated CI/CD via GitHub Actions, and Sentry error monitoring.

**Architecture:** Nginx reverse proxy (ports 80/443) routes `/api/*` to the FastAPI backend container and `/*` to a static-serving Nginx frontend container. Certbot runs alongside Nginx sharing a volume for Let's Encrypt certificates. GitHub Actions builds images, pushes to GHCR, and SSH-deploys to the Droplet on every push to `main`.

**Tech Stack:** Docker, Docker Compose, Nginx, Certbot/Let's Encrypt, sslip.io, GitHub Actions, GHCR, sentry-sdk[fastapi], @sentry/react

---

## File Map

| Action | Path |
|---|---|
| Create | `Dockerfile` |
| Create | `frontend/Dockerfile` |
| Create | `frontend/nginx.conf` |
| Create | `docker/nginx/nginx.conf` |
| Create | `docker/nginx/conf.d/app.http.conf` |
| Create | `docker/nginx/templates/app.conf.template` |
| Create | `docker/nginx/entrypoint.sh` |
| Create | `docker/docker-compose.prod.yml` |
| Create | `scripts/init-letsencrypt.sh` |
| Create | `scripts/backup-db.sh` |
| Create | `scripts/deploy.sh` |
| Create | `.env.prod.example` |
| Create | `.github/workflows/deploy.yml` |
| Modify | `pyproject.toml` — add sentry-sdk[fastapi] |
| Modify | `app/config/settings.py` — add sentry_dsn field |
| Modify | `app/main.py` — init Sentry in lifespan |
| Modify | `frontend/package.json` — add @sentry/react |
| Modify | `frontend/vite.config.ts` — expose VITE_SENTRY_DSN |
| Modify | `frontend/app/client.tsx` — init Sentry |
| Modify | `.gitignore` — add .env.prod |

---

## Task 1: Backend Dockerfile

**Files:**
- Create: `Dockerfile`

- [ ] **Step 1: Create Dockerfile**

```dockerfile
FROM python:3.12-slim

# Install system deps needed for healthcheck and psycopg
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first — Docker layer cache means deps only reinstall when these change
COPY pyproject.toml uv.lock ./

# Install dependencies (not the project itself yet) — no dev deps
RUN uv sync --frozen --no-install-project --no-dev

# Copy application code
COPY app/ ./app/
COPY migrations/ ./migrations/
COPY alembic.ini ./

# Install the project itself
RUN uv sync --frozen --no-dev

# Non-root user
RUN groupadd -r eva && useradd -r -g eva eva && chown -R eva:eva /app
USER eva

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=30s \
    CMD curl -f http://localhost:8000/health || exit 1

# Run migrations then start server
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

- [ ] **Step 2: Verify it builds locally**

```bash
docker build -t eva-backend-test .
```

Expected: `Successfully built <hash>` with no errors.

- [ ] **Step 3: Commit**

```bash
git add Dockerfile
git commit -m "feat: add backend Dockerfile with uv, non-root user, healthcheck"
```

---

## Task 2: Frontend Dockerfile + SPA Nginx config

**Files:**
- Create: `frontend/Dockerfile`
- Create: `frontend/nginx.conf`

- [ ] **Step 1: Create frontend/nginx.conf (SPA routing)**

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    # React SPA — unknown paths fall back to index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # No cache for index.html so new deployments are picked up immediately
    location = /index.html {
        add_header Cache-Control "no-cache";
    }
}
```

- [ ] **Step 2: Create frontend/Dockerfile**

```dockerfile
# Stage 1: Build React app
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --silent

COPY . .

# VITE_API_URL is injected at build time — Vite bakes it into the JS bundle
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL

ARG VITE_SENTRY_DSN=""
ENV VITE_SENTRY_DSN=$VITE_SENTRY_DSN

RUN npm run build

# Stage 2: Serve with Nginx
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

- [ ] **Step 3: Verify it builds locally**

```bash
cd frontend && docker build -t eva-frontend-test .
cd ..
```

Expected: `Successfully built <hash>` with no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/Dockerfile frontend/nginx.conf
git commit -m "feat: add frontend multi-stage Dockerfile with Nginx SPA serving"
```

---

## Task 3: Nginx reverse proxy config

**Files:**
- Create: `docker/nginx/nginx.conf`
- Create: `docker/nginx/conf.d/app.http.conf`
- Create: `docker/nginx/templates/app.conf.template`
- Create: `docker/nginx/entrypoint.sh`

- [ ] **Step 1: Create docker/nginx/nginx.conf**

```nginx
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    sendfile on;
    keepalive_timeout 65;
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
    include /etc/nginx/conf.d/*.conf;
}
```

- [ ] **Step 2: Create docker/nginx/conf.d/app.http.conf**

```nginx
server {
    listen 80;
    server_name _;

    # Certbot ACME challenge files (Let's Encrypt verification)
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    # Redirect all other HTTP traffic to HTTPS
    location / {
        return 301 https://$host$request_uri;
    }
}
```

- [ ] **Step 3: Create docker/nginx/templates/app.conf.template**

The `${DOMAIN}` placeholder is substituted by the entrypoint at startup. All other `$variable` patterns (nginx builtins like `$host`, `$remote_addr`) are left intact.

```nginx
server {
    listen 443 ssl;
    server_name ${DOMAIN};

    ssl_certificate /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # WebSocket — must be matched before the general /api/ location
    location /api/v1/voice/stream {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    # REST API
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Frontend (static files served by inner Nginx container)
    location / {
        proxy_pass http://frontend:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

- [ ] **Step 4: Create docker/nginx/entrypoint.sh**

```sh
#!/bin/sh
set -e

# Substitute only ${DOMAIN} — leave all other nginx $variables ($host, $remote_addr, etc.) intact
envsubst '${DOMAIN}' < /etc/nginx/templates/app.conf.template > /etc/nginx/conf.d/app.conf

# Auto-reload every 6h so Nginx picks up renewed Let's Encrypt certificates
# without requiring a manual restart or full redeploy
(while true; do sleep 6h; nginx -s reload; done) &

exec nginx -g 'daemon off;'
```

- [ ] **Step 5: Make entrypoint executable**

```bash
chmod +x docker/nginx/entrypoint.sh
```

- [ ] **Step 6: Commit**

```bash
git add docker/nginx/
git commit -m "feat: add Nginx reverse proxy config with SSL, WebSocket, and auto-reload"
```

---

## Task 4: docker-compose.prod.yml

**Files:**
- Create: `docker/docker-compose.prod.yml`

- [ ] **Step 1: Create docker/docker-compose.prod.yml**

```yaml
services:
  postgres:
    image: pgvector/pgvector:0.8.0-pg16
    restart: unless-stopped
    env_file: ../.env.prod
    environment:
      POSTGRES_USER: eva
      POSTGRES_DB: eva
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./postgres/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: pg_isready -U eva -d eva
      interval: 5s
      timeout: 3s
      retries: 5
      start_period: 10s
    mem_limit: 512m
    networks:
      - internal

  backend:
    image: ghcr.io/${GITHUB_USERNAME}/eva-backend:latest
    restart: unless-stopped
    env_file: ../.env.prod
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: curl -f http://localhost:8000/health || exit 1
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    mem_limit: 512m
    networks:
      - internal

  frontend:
    image: ghcr.io/${GITHUB_USERNAME}/eva-frontend:latest
    restart: unless-stopped
    mem_limit: 128m
    networks:
      - internal

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    entrypoint: ["/bin/sh", "/entrypoint.sh"]
    environment:
      - DOMAIN=${DOMAIN}
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/entrypoint.sh:/entrypoint.sh:ro
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/conf.d/app.http.conf:/etc/nginx/conf.d/app.http.conf:ro
      - ./nginx/templates/app.conf.template:/etc/nginx/templates/app.conf.template:ro
      - certbot-certs:/etc/letsencrypt:ro
      - certbot-www:/var/www/certbot:ro
    depends_on:
      backend:
        condition: service_healthy
      frontend:
        condition: service_started
    mem_limit: 128m
    networks:
      - internal

  certbot:
    image: certbot/certbot
    volumes:
      - certbot-certs:/etc/letsencrypt
      - certbot-www:/var/www/certbot
    # Attempt renewal every 12h — Let's Encrypt certs expire after 90 days
    entrypoint: /bin/sh -c "trap exit TERM; while :; do certbot renew; sleep 12h & wait $!; done"
    mem_limit: 64m
    networks:
      - internal

volumes:
  postgres-data:
  certbot-certs:
  certbot-www:
  backup-data:

networks:
  internal:
    driver: bridge
```

- [ ] **Step 2: Commit**

```bash
git add docker/docker-compose.prod.yml
git commit -m "feat: add docker-compose.prod.yml with all services, healthchecks, resource limits"
```

---

## Task 5: init-letsencrypt.sh

This script runs **once** on the server to bootstrap the first SSL certificate.

**Files:**
- Create: `scripts/init-letsencrypt.sh`

- [ ] **Step 1: Create scripts/init-letsencrypt.sh**

```bash
#!/bin/bash
# Run once on the Droplet to obtain the first Let's Encrypt certificate.
# After this, Certbot renews automatically every 12h.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker/docker-compose.prod.yml"
ENV_FILE="$ROOT_DIR/.env.prod"

# Load environment variables from .env.prod
if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: $ENV_FILE not found. Copy .env.prod.example to .env.prod and fill in values."
    exit 1
fi

set -a
source "$ENV_FILE"
set +a

if [ -z "$DOMAIN" ]; then
    echo "ERROR: DOMAIN is not set in .env.prod (e.g. eva.1.2.3.4.sslip.io)"
    exit 1
fi

if [ -z "$LETSENCRYPT_EMAIL" ]; then
    echo "ERROR: LETSENCRYPT_EMAIL is not set in .env.prod"
    exit 1
fi

echo "=== [1/5] Creating dummy self-signed certificate so Nginx can start ==="
docker compose -f "$COMPOSE_FILE" run --rm --entrypoint "sh" certbot -c "
    mkdir -p /etc/letsencrypt/live/$DOMAIN &&
    openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
        -keyout /etc/letsencrypt/live/$DOMAIN/privkey.pem \
        -out  /etc/letsencrypt/live/$DOMAIN/fullchain.pem \
        -subj '/CN=localhost' 2>/dev/null
"

echo "=== [2/5] Starting Nginx (HTTP only, with dummy cert) ==="
docker compose -f "$COMPOSE_FILE" up --force-recreate -d nginx frontend postgres
echo "Waiting 5s for Nginx to be ready..."
sleep 5

echo "=== [3/5] Deleting dummy certificate ==="
docker compose -f "$COMPOSE_FILE" run --rm --entrypoint "sh" certbot -c \
    "rm -rf /etc/letsencrypt/live/$DOMAIN"

echo "=== [4/5] Requesting real Let's Encrypt certificate for $DOMAIN ==="
docker compose -f "$COMPOSE_FILE" run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$LETSENCRYPT_EMAIL" \
    --agree-tos \
    --no-eff-email \
    -d "$DOMAIN"

echo "=== [5/5] Reloading Nginx with real certificate ==="
docker compose -f "$COMPOSE_FILE" exec nginx nginx -s reload

echo ""
echo "=== SSL certificate obtained successfully! Starting all services... ==="
docker compose -f "$COMPOSE_FILE" up -d

echo ""
echo "Your app is live at: https://$DOMAIN"
```

- [ ] **Step 2: Make executable and commit**

```bash
chmod +x scripts/init-letsencrypt.sh
git add scripts/init-letsencrypt.sh
git commit -m "feat: add init-letsencrypt.sh for first-time SSL certificate bootstrap"
```

---

## Task 6: backup-db.sh + deploy.sh

**Files:**
- Create: `scripts/backup-db.sh`
- Create: `scripts/deploy.sh`

- [ ] **Step 1: Create scripts/backup-db.sh**

```bash
#!/bin/bash
# Nightly database backup. Add to cron on the Droplet:
#   0 2 * * * root /opt/eva/scripts/backup-db.sh >> /var/log/eva-backup.log 2>&1

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/../docker/docker-compose.prod.yml"
BACKUP_DIR="/var/backups/eva"
DATE=$(date +%Y-%m-%d)

mkdir -p "$BACKUP_DIR"

echo "[$(date -Iseconds)] Starting backup..."

# pg_dump runs inside the postgres container, output piped to host file
docker compose -f "$COMPOSE_FILE" exec -T postgres \
    pg_dump -U eva eva > "$BACKUP_DIR/eva-$DATE.sql"

# Keep only the last 7 daily backups
find "$BACKUP_DIR" -name "eva-*.sql" -mtime +7 -delete

echo "[$(date -Iseconds)] Backup complete: $BACKUP_DIR/eva-$DATE.sql ($(du -sh "$BACKUP_DIR/eva-$DATE.sql" | cut -f1))"
```

- [ ] **Step 2: Create scripts/deploy.sh**

This script is called by GitHub Actions via SSH. It can also be run manually on the Droplet.

```bash
#!/bin/bash
# Pull latest images and restart containers.
# Called by GitHub Actions after new images are pushed to GHCR.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/../docker/docker-compose.prod.yml"

echo "[$(date -Iseconds)] Pulling latest images..."
docker compose -f "$COMPOSE_FILE" pull

echo "[$(date -Iseconds)] Restarting containers..."
docker compose -f "$COMPOSE_FILE" up -d

echo "[$(date -Iseconds)] Removing dangling images..."
docker image prune -f

echo "[$(date -Iseconds)] Deploy complete."
docker compose -f "$COMPOSE_FILE" ps
```

- [ ] **Step 3: Make executable and commit**

```bash
chmod +x scripts/backup-db.sh scripts/deploy.sh
git add scripts/backup-db.sh scripts/deploy.sh
git commit -m "feat: add backup-db.sh (nightly pg_dump) and deploy.sh scripts"
```

---

## Task 7: .env.prod.example

**Files:**
- Create: `.env.prod.example`

- [ ] **Step 1: Create .env.prod.example**

```bash
# Production environment — copy to .env.prod and fill in real values.
# NEVER commit .env.prod to git.

# === Server ===
DOMAIN=eva.YOUR_DROPLET_IP.sslip.io
LETSENCRYPT_EMAIL=your@email.com
GITHUB_USERNAME=your-github-username

# === Application ===
ENVIRONMENT=production
LOG_LEVEL=INFO
MOCK_AUTH_ENABLED=false

# === Database ===
# Use internal Docker hostname 'postgres' (not localhost)
DATABASE_URL=postgresql+asyncpg://eva:eva@postgres:5432/eva
POSTGRES_PASSWORD=change_this_to_a_strong_password
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=5

# === CORS ===
# Must match your DOMAIN exactly
CORS_ORIGINS=["https://eva.YOUR_DROPLET_IP.sslip.io"]

# === Google Gemini ===
GOOGLE_API_KEY=your_google_api_key_here
GEMINI_MODEL=gemini-2.0-flash
GEMINI_AUDIO_MODEL=gemini-2.5-flash-native-audio-dialog

# === Auth & JWT ===
JWT_SECRET=generate_with_openssl_rand_hex_32
JWT_ALGORITHM=HS256
ADMIN_SECRET_KEY=generate_with_openssl_rand_hex_32
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=https://eva.YOUR_DROPLET_IP.sslip.io/api/v1/auth/callback/google

# === Sentry (Error Monitoring — free at sentry.io) ===
SENTRY_DSN=https://your_key@sentry.io/your_project_id

# === Langfuse (LLM Observability — optional) ===
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com

# === Vector / Embeddings ===
EMBEDDING_MODEL=text-embedding-004
EMBEDDING_DIM=768
VECTOR_INDEX_TYPE=hnsw
HNSW_M=16
HNSW_EF_CONSTRUCTION=64
RETRIEVAL_TOP_K=5
MAX_TOOL_CALLS_PER_TURN=6
```

- [ ] **Step 2: Commit**

```bash
git add .env.prod.example
git commit -m "feat: add .env.prod.example with all production environment variables"
```

---

## Task 8: .gitignore update

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add .env.prod to .gitignore**

Open `.gitignore` and add after the `.env` line:

```
.env.prod
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: add .env.prod to .gitignore"
```

---

## Task 9: GitHub Actions deploy.yml

**Files:**
- Create: `.github/workflows/deploy.yml`

- [ ] **Step 1: Create .github/workflows/deploy.yml**

```yaml
name: Build and Deploy

on:
  push:
    branches: [main]

env:
  REGISTRY: ghcr.io
  BACKEND_IMAGE: ghcr.io/${{ github.repository_owner }}/eva-backend
  FRONTEND_IMAGE: ghcr.io/${{ github.repository_owner }}/eva-frontend

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build and push backend image
        uses: docker/build-push-action@v6
        with:
          context: .
          file: ./Dockerfile
          push: true
          tags: ${{ env.BACKEND_IMAGE }}:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Build and push frontend image
        uses: docker/build-push-action@v6
        with:
          context: ./frontend
          file: ./frontend/Dockerfile
          push: true
          tags: ${{ env.FRONTEND_IMAGE }}:latest
          build-args: |
            VITE_API_URL=https://${{ secrets.DOMAIN }}
            VITE_SENTRY_DSN=${{ secrets.VITE_SENTRY_DSN }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Deploy to Droplet via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.DROPLET_HOST }}
          username: root
          key: ${{ secrets.DROPLET_SSH_KEY }}
          script: |
            cd /opt/eva
            bash scripts/deploy.sh
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "feat: add GitHub Actions CI/CD pipeline — build, push GHCR, SSH deploy"
```

---

## Task 10: Sentry backend integration

**Files:**
- Modify: `pyproject.toml`
- Modify: `app/config/settings.py`
- Modify: `app/main.py`

- [ ] **Step 1: Add sentry-sdk to pyproject.toml**

In `pyproject.toml`, add to the `dependencies` list after `langfuse`:

```toml
"sentry-sdk[fastapi]>=2.0.0",
```

- [ ] **Step 2: Sync dependencies**

```bash
uv sync
```

Expected: uv resolves and installs `sentry-sdk` and its fastapi integration.

- [ ] **Step 3: Add sentry_dsn to settings.py**

In `app/config/settings.py`, add after `langfuse_base_url`:

```python
# Sentry error monitoring
sentry_dsn: str = ""
```

- [ ] **Step 4: Init Sentry in app/main.py**

At the top of `app/main.py`, after the existing imports, add:

```python
import sentry_sdk
```

Inside the `lifespan` function, add Sentry init **before** the Langfuse block:

```python
# ── Sentry Error Monitoring ─────────────────────────────────────────
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=0.1,  # 10% of requests traced for performance
    )
```

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock app/config/settings.py app/main.py
git commit -m "feat: add Sentry error monitoring to FastAPI backend"
```

---

## Task 11: Sentry frontend integration

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/app/client.tsx`

- [ ] **Step 1: Install @sentry/react**

```bash
cd frontend && npm install @sentry/react
cd ..
```

- [ ] **Step 2: Expose VITE_SENTRY_DSN in vite.config.ts**

In `frontend/vite.config.ts`, update the `define` block to include the Sentry DSN alongside the existing API URL:

```ts
define: {
    'process.env.VITE_API_URL': JSON.stringify(
      process.env.VITE_API_URL || 'http://localhost:8000',
    ),
    'process.env.VITE_SENTRY_DSN': JSON.stringify(
      process.env.VITE_SENTRY_DSN || '',
    ),
  },
```

- [ ] **Step 3: Init Sentry in frontend/app/client.tsx**

Add at the top of `frontend/app/client.tsx`, after the existing imports:

```tsx
import * as Sentry from '@sentry/react'

const sentryDsn = process.env.VITE_SENTRY_DSN
if (sentryDsn) {
  Sentry.init({
    dsn: sentryDsn,
    environment: process.env.VITE_API_URL?.startsWith('https') ? 'production' : 'development',
    tracesSampleRate: 0.1,
  })
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vite.config.ts frontend/app/client.tsx
git commit -m "feat: add Sentry error monitoring to React frontend"
```

---

## Task 12: Local smoke test (build both images)

Verify both images build cleanly before pushing to CI.

- [ ] **Step 1: Build backend image**

```bash
docker build -t eva-backend:smoke-test .
```

Expected: `Successfully built <hash>` — no errors.

- [ ] **Step 2: Build frontend image**

```bash
docker build -t eva-frontend:smoke-test ./frontend
```

Expected: `Successfully built <hash>` — no errors.

- [ ] **Step 3: Run backend healthcheck locally**

```bash
docker run --rm -d --name eva-test \
  -e DATABASE_URL=postgresql+asyncpg://eva:eva@localhost:5432/eva \
  -e GOOGLE_API_KEY=placeholder \
  -p 8001:8000 \
  eva-backend:smoke-test

sleep 5
curl -f http://localhost:8001/health && echo "PASS" || echo "FAIL"
docker stop eva-test
```

Expected: `{"status":"ok","env":"development"}` then `PASS`.
Note: The DB won't be available so alembic will fail — expected. This just checks the image boots.

- [ ] **Step 4: Clean up test images**

```bash
docker rmi eva-backend:smoke-test eva-frontend:smoke-test
```

---

## Post-Implementation: Server Setup Guide

These steps are done **manually on the Droplet once** — not automated.

### 1. Create and access Droplet

```bash
# In DigitalOcean dashboard: Create Droplet → Ubuntu 24.04 → 2GB/1CPU → Add SSH key
ssh root@YOUR_DROPLET_IP
```

### 2. Install Docker on the Droplet

```bash
curl -fsSL https://get.docker.com | sh
```

### 3. Clone repo and configure

```bash
mkdir -p /opt/eva
cd /opt/eva
git clone https://github.com/YOUR_GITHUB_USERNAME/YOUR_REPO_NAME .

cp .env.prod.example .env.prod
nano .env.prod  # fill in all values, especially DOMAIN and POSTGRES_PASSWORD
```

### 4. Log in to GHCR on the Droplet

```bash
# Generate a GitHub PAT with read:packages scope at github.com/settings/tokens
echo YOUR_GITHUB_PAT | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
```

### 5. Run init-letsencrypt.sh

```bash
bash /opt/eva/scripts/init-letsencrypt.sh
```

### 6. Set up nightly backup cron

```bash
echo "0 2 * * * root /opt/eva/scripts/backup-db.sh >> /var/log/eva-backup.log 2>&1" \
  > /etc/cron.d/eva-backup
chmod 644 /etc/cron.d/eva-backup
```

### 7. Add GitHub Secrets (repo → Settings → Secrets → Actions)

| Secret name | Value |
|---|---|
| `DROPLET_HOST` | Droplet IP |
| `DROPLET_SSH_KEY` | Private SSH key content (`cat ~/.ssh/id_ed25519`) |
| `DOMAIN` | `eva.YOUR_DROPLET_IP.sslip.io` |
| `VITE_SENTRY_DSN` | Sentry DSN from sentry.io |

### 8. Create Sentry account (free)

1. Go to [sentry.io](https://sentry.io) → Sign up (free)
2. Create two projects: one **FastAPI** (Python), one **React**
3. Copy each DSN
4. Put backend DSN in `.env.prod` as `SENTRY_DSN=`
5. Put frontend DSN in GitHub Secrets as `VITE_SENTRY_DSN=`

### 9. Trigger first CI/CD deploy

```bash
# On your local machine:
git push origin main
```

Watch the GitHub Actions tab — first build takes ~5 min, subsequent builds use cache (~2 min).
