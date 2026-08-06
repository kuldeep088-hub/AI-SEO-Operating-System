#!/usr/bin/env bash
# Start everything. Ctrl-C stops all of it.
set -euo pipefail
cd "$(dirname "$0")"

[ -f .env ] || { echo "No .env — run ./setup.sh first."; exit 1; }
set -a; source .env; set +a

# See setup.sh: this project's path has spaces, which several tools mishandle.
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$HOME/.seoos/venv}"

# apps/web's `dev` script delegates back to this file so that `npm run dev` can never
# start the web app without the API behind it. This is the flag that breaks the loop —
# see apps/web/scripts/dev.mjs.
export SEOOS_STACK=1

PROD=0
if [ "${1:-}" = "--prod" ]; then
  PROD=1
  # Structured JSON logs to logs/app.log, no reloader, built web bundle.
  # The session cookie's Secure flag follows API_URL's scheme, not this — see
  # packages/core/config.py — so prod mode on plain-http localhost still works.
  export ENV=prod-local
fi

mkdir -p logs

cleanup() {
  echo
  echo "Stopping…"
  kill 0 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "▸ Postgres"
# Two URLs on purpose. The app runs as seoos_app, which is neither superuser nor
# table owner, so the RLS policies actually apply to it — a superuser connection
# bypasses RLS entirely and every org sees every other org's rows, silently.
# Alembic needs the owner, because seoos_app has no CREATE.
DB_URL="$(uv run python scripts/pg.py start | tail -1)"
export DATABASE_URL="$DB_URL"
export ADMIN_DATABASE_URL="$(uv run python scripts/pg.py admin-url | tail -1)"
echo "  $DB_URL"

echo "▸ Ollama"
if [ -x ./bin/ollama ]; then
  if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    ./bin/ollama serve >logs/ollama.log 2>&1 &
    until curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; do sleep 0.3; done
  fi
  echo "  ready"
else
  echo "  bin/ollama missing — AI features will be unavailable. Run ./setup.sh."
fi

echo "▸ API"
if [ $PROD -eq 1 ]; then
  uv run uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 &
else
  uv run uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --reload &
fi

echo "▸ Worker"
uv run python -m apps.worker.main &

echo "▸ Web"
if [ $PROD -eq 1 ]; then
  (cd apps/web && npm run build && npm run start) &
else
  (cd apps/web && npm run dev) &
fi

sleep 3
cat <<EOF

  ┌──────────────────────────────────────────────┐
  │  Dashboard   http://localhost:3000           │
  │  API docs    http://localhost:8000/v1/docs   │
  │  Health      http://localhost:8000/health    │
  └──────────────────────────────────────────────┘

  Ctrl-C stops everything.

EOF

wait
