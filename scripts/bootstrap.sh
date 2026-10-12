#!/usr/bin/env bash
# Clean local install: infra, dependencies (lockfiles), migrations, bucket, pinned model weights.
# Prerequisites: Docker (compose v2), Node >= 23.6, uv, ffmpeg. No GPU required.
set -euo pipefail
cd "$(dirname "$0")/.."
for c in docker node npm uv ffmpeg ffprobe; do command -v "$c" >/dev/null || { echo "missing prerequisite: $c" >&2; exit 1; }; done
node -e 'const [a,b]=process.versions.node.split(".").map(Number); if (a<23||(a===23&&b<6)) { console.error("Node >= 23.6 required"); process.exit(1) }'
[ -f .env ] || cp .env.example .env
docker compose up -d --wait postgres s3
docker compose up -d keycloak mailpit prometheus alertmanager grafana
npm ci --no-audit --no-fund
(cd py && uv sync --frozen)
for i in $(seq 1 60); do node scripts/migrate.mjs && break; sleep 2; done
(cd py && uv run python -c "from huggingface_hub import snapshot_download; print(snapshot_download('google/embeddinggemma-2', revision='914f7f89142e33e77833254d9c9b90c3cef7303b')); print(snapshot_download('Systran/faster-whisper-base', revision='ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66'))")
for i in $(seq 1 90); do curl -sf http://localhost:8180/realms/kb/.well-known/openid-configuration >/dev/null && break; sleep 2; done
echo "bootstrap complete"
