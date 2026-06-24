#!/bin/sh
set -e

# Substitute only ${DOMAIN} — leave all other nginx $variables ($host, $remote_addr, etc.) intact
envsubst '${DOMAIN}' < /etc/nginx/templates/app.conf.template > /etc/nginx/conf.d/app.conf

# Auto-reload every 6h so Nginx picks up renewed Let's Encrypt certificates
# without requiring a manual restart or full redeploy
(while true; do sleep 6h; nginx -s reload; done) &

exec nginx -g 'daemon off;'
