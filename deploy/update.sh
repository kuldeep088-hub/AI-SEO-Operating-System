#!/usr/bin/env bash
# Deploy, and also the update path. Run as root after bootstrap.sh and .env.
#
#   /opt/seoos/app/deploy/update.sh
#
# setup.sh is NOT used on a server: it installs Ollama.app, bundles pgserver,
# and works around the Mac's spaces-in-path problem. This is the Linux
# equivalent — start Postgres, migrate, build, restart.
set -euo pipefail

APP_DIR=/opt/seoos/app
cd "$APP_DIR"
[ -f .env ] || { echo "no $APP_DIR/.env — see deploy/README.md §3" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || { echo "run as root" >&2; exit 1; }

export UV_PROJECT_ENVIRONMENT=/opt/seoos/venv
set -a; source .env; set +a

step() { printf '\n\033[1m▸ %s\033[0m\n' "$1"; }

: "${API_URL:?API_URL must be set}"
: "${DATABASE_URL:?DATABASE_URL must be set}"
: "${ADMIN_DATABASE_URL:?ADMIN_DATABASE_URL must be set — Alembic needs the owner}"

case "$API_URL" in
    https://*) ;;
    *) echo "API_URL must be https:// — the session cookie's Secure flag derives"
       echo "from its scheme (packages/core/config.py cookie_secure)." >&2; exit 1 ;;
esac
case "$DATABASE_URL" in
    *//seoos_app:*) ;;
    *) echo "DATABASE_URL must connect as seoos_app. As owner or superuser the"
       echo "RLS policies do not apply and tenants read each other's data." >&2
       exit 1 ;;
esac

: "${WEB_URL:?WEB_URL must be set}"
# One hostname for both, or the browser treats the API call as cross-site and
# silently drops the session cookie — login "works", every page then acts
# logged out, and nothing appears in any log. deploy/Caddyfile exists precisely
# to serve /v1/* and the web app from a single name; this guard is what stops
# .env from quietly contradicting it.
if [ "$WEB_URL" != "$API_URL" ]; then
    echo "WEB_URL ($WEB_URL) and API_URL ($API_URL) must be the same origin." >&2
    echo "Caddy serves /v1/* and the web app from one hostname; split them and" >&2
    echo "the session cookie is dropped on every API call, with no error." >&2
    exit 1
fi

step "Code"
if [ -d .git ]; then
    sudo -u seoos git pull --ff-only
else
    echo "  not a git checkout — assuming files were copied in place"
fi

step "Postgres"
# The repo-root docker-compose.yml. Prometheus and Grafana sit behind the
# `metrics` profile, so this starts Postgres alone.
docker compose up -d postgres
until docker compose exec -T postgres pg_isready -U seoos -d seoos >/dev/null 2>&1; do
    sleep 1
done

# infra/postgres/init.sql creates seoos_app with a hardcoded development
# password. Rotate it to whatever DATABASE_URL actually carries, every run, so
# the two can never drift apart.
APP_PW="$(python3 -c '
import os, sys
from urllib.parse import urlsplit, unquote
print(unquote(urlsplit(os.environ["DATABASE_URL"]).password or ""))
')"
if [ -n "$APP_PW" ]; then
    docker compose exec -T postgres psql -U seoos -d seoos -v ON_ERROR_STOP=1 -q \
        -c "ALTER ROLE seoos_app LOGIN PASSWORD '$(printf '%s' "$APP_PW" | sed "s/'/''/g")'"
fi

step "Python dependencies"
sudo -u seoos env UV_PROJECT_ENVIRONMENT=/opt/seoos/venv uv sync --all-extras

step "Migrations"
# ADMIN_DATABASE_URL, not DATABASE_URL — seoos_app has no CREATE privilege.
sudo -u seoos env UV_PROJECT_ENVIRONMENT=/opt/seoos/venv \
    DATABASE_URL="$DATABASE_URL" ADMIN_DATABASE_URL="$ADMIN_DATABASE_URL" \
    uv run alembic upgrade head

step "Tenant isolation check"
# Before serving traffic, not after. tests/isolation is the suite that catches
# an app connected as the wrong role — the failure that leaks one client's data
# to another with no error anywhere.
sudo -u seoos env UV_PROJECT_ENVIRONMENT=/opt/seoos/venv \
    DATABASE_URL="$DATABASE_URL" ADMIN_DATABASE_URL="$ADMIN_DATABASE_URL" \
    uv run pytest tests/isolation -q

step "Web build"
# API_URL must be exported HERE. next.config.mjs inlines it into the browser
# bundle at build time, so building without it ships localhost:8000 to real
# users — the sign-in link and the connect form both break, and it looks like a
# server fault rather than a build one.
sudo -u seoos env API_URL="$API_URL" WEB_URL="$WEB_URL" NODE_ENV=production \
    sh -c 'cd /opt/seoos/app/apps/web && npm ci && npm run build'

step "Restart"
systemctl restart seoos-api seoos-worker seoos-web
systemctl reload caddy || systemctl restart caddy

step "Health"
for _ in $(seq 1 30); do
    if curl -sf http://127.0.0.1:8000/health >/dev/null; then break; fi
    sleep 1
done
curl -s http://127.0.0.1:8000/health | jq . || {
    echo "API did not come up. journalctl -u seoos-api -n 50" >&2
    exit 1
}

printf '\n  ✓ %s\n\n' "$API_URL"
