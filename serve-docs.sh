#!/usr/bin/env bash
# Read the AI SEO OS documentation at http://localhost:4000
# No dependencies beyond python3 (ships with macOS).

set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-4000}"

# Fail early with a useful message rather than a stack trace.
if lsof -Pi ":$PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
  echo "Port $PORT is already in use."
  echo "Either stop what's using it, or run:  PORT=4001 ./serve-docs.sh"
  exit 1
fi

echo "AI SEO Operating System — documentation"
echo "  http://localhost:$PORT/README.md"
echo "  http://localhost:$PORT/docs/"
echo
echo "Ctrl-C to stop."
echo

# Open the browser once the server is actually accepting connections.
( until curl -sf "http://localhost:$PORT/" >/dev/null 2>&1; do sleep 0.2; done
  open "http://localhost:$PORT/README.md" ) &

exec python3 -m http.server "$PORT" --bind 127.0.0.1
