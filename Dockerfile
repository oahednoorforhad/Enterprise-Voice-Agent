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
