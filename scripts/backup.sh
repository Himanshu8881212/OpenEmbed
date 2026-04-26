#!/usr/bin/env bash
# Snapshot EMBEd's two stateful stores into a single timestamped tarball.
#
#   chroma_db/  — vector store (the embeddings themselves)
#   embed.db    — SQLite vault + file metadata
#
# Usage:
#   ./scripts/backup.sh                    # writes to ./backups/
#   ./scripts/backup.sh /mnt/snapshots     # writes to a custom dir
#
# Env:
#   BACKUP_RETENTION_DAYS  default 30 — older tarballs in the dir are pruned
#
# Restore:
#   1. Stop the EMBEd server.
#   2. tar -xzf backups/embed-YYYY-MM-DD-HHMMSS.tgz -C /tmp/restore
#   3. Replace ./chroma_db and ./embed.db with the extracted copies.
#   4. Start the server.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${1:-$ROOT/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
STAMP="$(date +%Y-%m-%d-%H%M%S)"
NAME="embed-${STAMP}.tgz"

mkdir -p "$DEST"

cd "$ROOT"
TARGETS=()
[[ -d chroma_db ]] && TARGETS+=("chroma_db")
[[ -f embed.db ]]  && TARGETS+=("embed.db")
# Capture SQLite WAL/SHM if present so the restore is consistent.
[[ -f embed.db-wal ]] && TARGETS+=("embed.db-wal")
[[ -f embed.db-shm ]] && TARGETS+=("embed.db-shm")

if [[ ${#TARGETS[@]} -eq 0 ]]; then
    echo "nothing to back up — neither chroma_db/ nor embed.db exist in $ROOT"
    exit 0
fi

echo "→ snapshotting: ${TARGETS[*]}"
tar -czf "$DEST/$NAME" "${TARGETS[@]}"
SIZE=$(du -h "$DEST/$NAME" | cut -f1)
echo "✓ wrote $DEST/$NAME ($SIZE)"

# Prune old snapshots.
PRUNED=$(find "$DEST" -maxdepth 1 -type f -name 'embed-*.tgz' -mtime "+${RETENTION_DAYS}" -print -delete | wc -l | tr -d ' ')
if [[ "$PRUNED" != "0" ]]; then
    echo "✓ pruned $PRUNED snapshot(s) older than ${RETENTION_DAYS}d"
fi
