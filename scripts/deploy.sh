#!/bin/bash
# Pull latest images and restart containers.
# Called by GitHub Actions after new images are pushed to GHCR.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker/docker-compose.prod.yml"
ENV_FILE="$ROOT_DIR/.env.prod"

# Load environment variables so docker compose can use ${GITHUB_USERNAME}, ${DOMAIN}, etc.
if [ -f "$ENV_FILE" ]; then
  set -a
  source "$ENV_FILE"
  set +a
fi

echo "[$(date -Iseconds)] Pulling latest images..."
docker compose -f "$COMPOSE_FILE" pull

echo "[$(date -Iseconds)] Restarting containers..."
docker compose -f "$COMPOSE_FILE" up -d

echo "[$(date -Iseconds)] Removing dangling images..."
docker image prune -f

echo "[$(date -Iseconds)] Deploy complete."
docker compose -f "$COMPOSE_FILE" ps
