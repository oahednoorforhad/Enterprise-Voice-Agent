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
