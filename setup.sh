#!/usr/bin/env bash
# Install / update everything. Idempotent — safe to re-run.
# No sudo, no Homebrew, no admin rights.
set -euo pipefail
cd "$(dirname "$0")"

step() { printf "\n\033[1;32m▸\033[0m %s\n" "$1"; }
warn() { printf "\033[1;33m  ! %s\033[0m\n" "$1"; }
need() { command -v "$1" >/dev/null || { printf "\033[1;31mMissing: %s\033[0m — %s\n" "$1" "$2"; exit 1; }; }

# This project's path contains spaces ("Growleads AI SEO "). Several tools —
# postgres' -o options string, pgserver's psql invocation — word-split unquoted
# paths and break. Keeping the venv on a space-free path avoids all of it.
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$HOME/.seoos/venv}"

step "Checking prerequisites"
need node    "install Node 20+ from nodejs.org"
need python3 "macOS ships python3; install Xcode Command Line Tools if missing"
need uv      "curl -LsSf https://astral.sh/uv/install.sh | sh"
echo "  node $(node -v) · uv $(uv --version | cut -d' ' -f2)"
if command -v docker >/dev/null && docker info >/dev/null 2>&1; then
  echo "  docker running — will use Docker Compose for Postgres"
else
  echo "  docker not available — will use bundled Postgres (pgserver)"
fi

step "Locating Ollama"
# Ollama.app installs to ~/Applications and is NOT added to PATH.
APP_OLLAMA="$HOME/Applications/Ollama.app/Contents/Resources/ollama"
if command -v ollama >/dev/null; then
  OLLAMA="$(command -v ollama)"
elif [ -x "$APP_OLLAMA" ]; then
  OLLAMA="$APP_OLLAMA"
else
  echo "  Downloading Ollama…"
  curl -fsSL https://ollama.com/download/Ollama-darwin.zip -o /tmp/ollama.zip
  unzip -q -o /tmp/ollama.zip -d "$HOME/Applications"
  OLLAMA="$APP_OLLAMA"
fi
mkdir -p bin && ln -sf "$OLLAMA" bin/ollama
echo "  ollama → $OLLAMA"

step "Pulling models (resumable; skips what you already have)"
STARTED_OLLAMA=""
if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  "$OLLAMA" serve >/dev/null 2>&1 &
  STARTED_OLLAMA=$!
  until curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; do sleep 0.3; done
fi
"$OLLAMA" pull qwen3.5:9b
"$OLLAMA" pull nomic-embed-text
[ -n "$STARTED_OLLAMA" ] && kill "$STARTED_OLLAMA" 2>/dev/null || true

step "Writing .env"
if [ ! -f .env ]; then
  cp .env.example .env
  python3 - <<'PY'
import base64, os, pathlib, secrets
p = pathlib.Path(".env")
vals = {
    "TOKEN_ENCRYPTION_KEY": base64.urlsafe_b64encode(os.urandom(32)).decode(),
    "SESSION_SECRET": secrets.token_urlsafe(48),
}
lines = []
for line in p.read_text().splitlines():
    key = line.split("=", 1)[0]
    lines.append(f"{key}={vals[key]}" if key in vals else line)
p.write_text("\n".join(lines) + "\n")
PY
  warn "Generated encryption keys in .env. Never commit it —"
  warn "losing TOKEN_ENCRYPTION_KEY orphans every stored OAuth connection."
else
  echo "  .env exists — leaving it alone."
fi

step "Python environment"
echo "  venv → $UV_PROJECT_ENVIRONMENT"
uv sync --all-extras

step "Starting Postgres"
DB_URL="$(uv run python scripts/pg.py start | tail -1)"
ADMIN_URL="$(uv run python scripts/pg.py admin-url | tail -1)"
echo "  $DB_URL"
# DATABASE_URL is the least-privilege app role (RLS applies); ADMIN_DATABASE_URL
# is the owner, used by Alembic only. Writing both, and appending either if the
# .env predates the split.
python3 - "$DB_URL" "$ADMIN_URL" <<'PY'
import pathlib, sys
app_url, admin_url = sys.argv[1], sys.argv[2]
p = pathlib.Path(".env")
lines = p.read_text().splitlines()
wanted = {"DATABASE_URL": app_url, "ADMIN_DATABASE_URL": admin_url}
seen = set()
out = []
for line in lines:
    key = line.split("=", 1)[0]
    if key in wanted:
        out.append(f"{key}={wanted[key]}")
        seen.add(key)
    else:
        out.append(line)
for key, value in wanted.items():
    if key not in seen:
        out.append(f"{key}={value}")
p.write_text("\n".join(out) + "\n")
PY

step "Running migrations"
set -a; source .env; set +a
uv run alembic upgrade head

step "Verifying tenant isolation"
uv run pytest tests/isolation -q

step "Web dependencies"
(cd apps/web && npm install --no-fund --no-audit)

printf "\n\033[1;32m✓ Setup complete.\033[0m\n\n"
if grep -q '^GOOGLE_CLIENT_ID=$' .env; then
  printf "  \033[1;33mNext: add Google OAuth credentials to .env\033[0m\n"
  printf "  See docs/14-execution.md §60. Without them you can start the app,\n"
  printf "  but sign-in will return a clear 503.\n\n"
fi
printf "  Then: ./run.sh\n\n"
