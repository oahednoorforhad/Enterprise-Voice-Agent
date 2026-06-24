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
