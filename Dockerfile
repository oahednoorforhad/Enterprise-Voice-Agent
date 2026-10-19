# Stage 1: build the React SPA (served by FastAPI from /app/static)
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --silent
COPY frontend/ .
# Empty VITE_API_URL = same origin as the page
RUN VITE_API_URL= npm run build

# Stage 2: backend
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock README.md alembic.ini ./
COPY app/ ./app/
COPY data/ ./data/
COPY migrations/ ./migrations/

RUN uv sync --frozen --no-dev

COPY --from=web /web/dist ./static

RUN groupadd -r eva && useradd -r -g eva eva && chown -R eva:eva /app
USER eva

ENV PATH="/app/.venv/bin:$PATH" PORT=8000

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'"]
