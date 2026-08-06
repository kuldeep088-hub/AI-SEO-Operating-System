#!/usr/bin/env bash
# One archive: database + data/ + .env.
# Treat the output as a SECRET — it contains TOKEN_ENCRYPTION_KEY.
set -euo pipefail
cd "$(dirname "$0")"
set -a; source .env; set +a

mkdir -p backups
STAMP=$(date +%Y-%m-%d-%H%M)
OUT="backups/seo-os-$STAMP.tar.zst"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

echo "▸ Dumping database"
docker compose exec -T postgres pg_dump -U seoos -d seoos --format=custom > "$TMP/db.dump"

echo "▸ Archiving"
tar --use-compress-program=zstd -cf "$OUT" \
    -C . $([ -d data ] && echo data) .env \
    -C "$TMP" db.dump

echo
echo "  ✓ $OUT  ($(du -h "$OUT" | cut -f1))"
echo
echo "  ⚠ This archive contains .env, including TOKEN_ENCRYPTION_KEY."
echo "    Anyone with it can decrypt every stored OAuth token. Store it"
echo "    somewhere you'd store a password, not somewhere you'd store a file."
echo
echo "  Restore:  see docs/12-roadmap.md §49 — and rehearse it before you need it."
