#!/usr/bin/env bash
# Restore a backup made by scripts/backup.sh, then replay deletions recorded after it. Stop workers first.
set -euo pipefail
cd "$(dirname "$0")/.."
DIR="$1"
docker compose exec -T postgres pg_restore --clean --if-exists --single-transaction -U kb_owner -d kb < "$DIR/db.dump"
node scripts/objects.mjs import "$DIR/objects"
node scripts/reapply-deletions.mjs "$(cat "$DIR/TIMESTAMP")"
