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
