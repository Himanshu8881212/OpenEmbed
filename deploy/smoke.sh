#!/usr/bin/env bash
# Smoke test of the container deployment: stack from images → ingest + search through API/worker/inference containers.
# Uses a throwaway env and an API key inserted directly (no IdP needed). Usage: deploy/smoke.sh   (port 3100)
set -euo pipefail
cd "$(dirname "$0")/.."
ENV=$(mktemp)
rand() { node -e 'console.log(require("crypto").randomBytes(18).toString("base64url"))'; }
cat > "$ENV" <<EOF
KB_PG_OWNER_PASSWORD=$(rand)
KB_PG_API_PASSWORD=$(rand)
KB_PG_WORKER_PASSWORD=$(rand)
KB_S3_ACCESS_KEY=kbdevaccess
KB_S3_SECRET_KEY=kbdevsecret
KB_OIDC_ISSUER=http://localhost:8180/realms/kb
KB_INFERENCE_TOKEN=$(rand)
KB_PUBLIC_BASE_URL=http://localhost:3100
KB_API_PORT=3100
KB_DEFAULT_PLAN={"name":"smoke","allow_excess":false,"limits":{"storage_bytes":1073741824,"index_tokens_month":1000000,"query_tokens_month":1000000}}
EOF
[ -f deploy/s3.json ] || cp deploy/s3.json.example deploy/s3.json
C="docker compose --env-file $ENV -f deploy/compose.yml"
[ -n "${KEEP:-}" ] || trap '$C down -v >/dev/null 2>&1; rm -f "$ENV"' EXIT
# reuse the host's pinned weights to avoid a 1.5 GB download in the smoke test
$C up -d postgres s3
$C run --rm migrate
$C run --rm --no-deps --user root -v "$HOME/.cache/huggingface/hub/models--google--embeddinggemma-2:/src:ro" inference \
  sh -c 'mkdir -p /models/hub/models--google--embeddinggemma-2 && cp -a /src/. /models/hub/models--google--embeddinggemma-2/ && chown -R kb /models'
$C up -d inference worker api
for i in $(seq 1 120); do curl -sf localhost:3100/readyz >/dev/null && break; sleep 3; done
curl -sf localhost:3100/readyz; echo
KEY="kb_smoke_$(rand)"
HASH=$(printf %s "$KEY" | shasum -a 256 | cut -d' ' -f1)
STORE=$($C exec -T postgres psql -U kb_owner kb -Atc "
  WITH w AS (INSERT INTO workspaces (name, plan) VALUES ('smoke', '{\"name\":\"smoke\",\"allow_excess\":true,\"limits\":{\"storage_bytes\":1073741824,\"index_tokens_month\":1000000,\"query_tokens_month\":1000000}}') RETURNING id),
       s AS (INSERT INTO stores (workspace_id, name) SELECT id, 'smoke' FROM w RETURNING id, workspace_id),
       r AS (INSERT INTO index_revisions (workspace_id, store_id, profile_id, state) SELECT workspace_id, id, 'eg2-914f7f8-fp32-p1', 'active' FROM s RETURNING id, store_id)
  SELECT store_id FROM r;" | head -1)
$C exec -T postgres psql -U kb_owner kb -qc "UPDATE stores SET active_revision_id = (SELECT id FROM index_revisions WHERE store_id='$STORE') WHERE id='$STORE';
  INSERT INTO api_keys (workspace_id, name, prefix, token_hash, scopes, store_ids) SELECT workspace_id, 'smoke', left('$KEY',10), decode('$HASH','hex'), '{search,source:read,source:write}', ARRAY['$STORE'::uuid] FROM stores WHERE id='$STORE';"
KB_BASE_URL=http://localhost:3100 KB_API_KEY=$KEY KB_CONFIG_DIR=$(mktemp -d) node cli/kb.ts ingest "$STORE" tests/fixtures/corpus/manuals --yes --wait
KB_BASE_URL=http://localhost:3100 KB_API_KEY=$KEY KB_CONFIG_DIR=$(mktemp -d) node cli/kb.ts search "$STORE" "How do I replace the pressure sensor?" --limit 2
echo "deploy smoke passed"
