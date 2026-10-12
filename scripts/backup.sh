#!/usr/bin/env bash
# Local backup drill: database (pg_dump custom format) + object storage (except ledger/). Prints the backup directory.
# Production: use managed PITR for PostgreSQL and bucket versioning/replication; keep the ledger/ prefix outside restores.
set -euo pipefail
cd "$(dirname "$0")/.."
DIR="${1:-backups/$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$DIR"
date -u +%Y-%m-%dT%H:%M:%S.000Z > "$DIR/TIMESTAMP"
docker compose exec -T postgres pg_dump -Fc -U kb_owner kb > "$DIR/db.dump"
node scripts/objects.mjs export "$DIR/objects" >&2
echo "$DIR"
