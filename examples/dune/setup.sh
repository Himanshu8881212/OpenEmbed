#!/usr/bin/env bash
# DUNE Bags demo (user: alice). Builds every store shape from ONE embedded base store, without re-uploading or re-embedding:
#   base store    dune-bags            whole folder (docx info sheets, renders, turntable frames, mp4)
#   split (views) dune-<bag>           one live view per sub-folder (via metadata bag=<name> + `stores split`)
#   merge         dune-sirocco-mirage  two split stores combined (dedup, vectors reused)
#   snapshot      dune-info-sheets     the three info sheets, frozen at their current versions
#   nested view   dune-sahara-renders  view over the Sahara view: studio renders only
#   export        .kb/dune-bags.jsonl  every segment with source, location, text and 768-d embedding
#   app key       .kb/app.key          search + source:read on all demo stores (used by rag.py)
# Prerequisite: `kb ingest dune-bags "$HOME/Downloads/DUNE Bags"` finished (see README.md).
set -euo pipefail
cd "$(dirname "$0")/../.."
export KB_CONFIG_DIR="$PWD/examples/dune/.kb"
KB="node cli/kb.ts"
OUT=examples/dune/.kb

login() { # dev IdP password grant for alice (production uses `kb auth login`, the device flow)
  local t; t=$(curl -sf -d grant_type=password -d client_id=kb-test -d username=alice@example.com -d password=dev-alice-password -d scope="openid email" \
    http://localhost:8180/realms/kb/protocol/openid-connect/token | python3 -c 'import json,sys;print(json.load(sys.stdin)["access_token"])')
  python3 -c "import json,sys,time;json.dump({'access_token':sys.argv[1],'expires_at':int(time.time()*1000)+840000},open('$OUT/credentials.json','w'))" "$t"
  chmod 600 "$OUT/credentials.json"
}
login
BASE=$($KB stores list --json | python3 -c 'import json,sys;print([s["id"] for s in json.load(sys.stdin)["data"] if s["name"]=="dune-bags"][0])')

echo "== 1. tag sources by sub-folder (bag) and kind"
KB_API_KEY=$(cat $OUT/importer.key) BASE=$BASE python3 - <<'PY'
import json, os, time, urllib.request
H = {"authorization": f"Bearer {os.environ['KB_API_KEY']}", "content-type": "application/json"}
def call(m, p, b=None):
    r = urllib.request.Request("http://localhost:3000" + p, method=m, headers=H, data=json.dumps(b).encode() if b is not None else None)
    return json.load(urllib.request.urlopen(r))
files, cursor = [], None
while True:
    r = call("GET", f"/v1/stores/{os.environ['BASE']}/files?limit=200" + (f"&cursor={cursor}" if cursor else ""))
    files += r["data"]; cursor = r["next_cursor"]
    if not cursor: break
for f in files:
    bag = f["path"].split(" - ")[0]
    name = f["path"].rsplit("/", 1)[-1]
    kind = "info" if name.endswith("_info.docx") else "video" if name.endswith(".mp4") else "frame" if "/frames/" in f["path"] else "render"
    if f["metadata"].get("bag") != bag or f["metadata"].get("kind") != kind:
        call("PATCH", f"/v1/files/{f['id']}", {"metadata": {"bag": bag, "kind": kind}})
        time.sleep(0.12)  # stay well under the per-minute rate limit
print(f"tagged {len(files)} sources")
PY

echo "== 2. split into one live view per bag"
$KB stores split dune-bags --field bag --prefix dune

echo "== 3. merge two of them"
login
$KB stores merge dune-sirocco dune-mirage --into dune-sirocco-mirage --wait

echo "== 4. snapshot of the info sheets"
echo '{"metadata":{"kind":"info"}}' > $OUT/info.json
$KB stores derive dune-bags --name dune-info-sheets --mode snapshot --filter @$OUT/info.json

echo "== 5. nested live view (view over the Sahara view): renders only"
echo '{"metadata":{"kind":"render"}}' > $OUT/render.json
$KB stores derive dune-sahara --name dune-sahara-renders --mode view --filter @$OUT/render.json

echo "== 6. export the base store's embeddings"
$KB stores export dune-bags -o $OUT/dune-bags.jsonl

echo "== 7. application key for the RAG program (search + source:read, restricted to the demo stores)"
STORES=(dune-bags dune-sirocco dune-mirage dune-sahara dune-sirocco-mirage dune-info-sheets dune-sahara-renders)
ARGS=(); for s in "${STORES[@]}"; do ARGS+=(--store "$s"); done
$KB keys create "${ARGS[@]}" --scope search,source:read --name dune-rag --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["secret"])' > $OUT/app.key
chmod 600 $OUT/app.key
$KB stores list --json | python3 -c '
import json,sys
d={s["name"]:s["id"] for s in json.load(sys.stdin)["data"] if s["name"].startswith("dune")}
json.dump(d,open("examples/dune/.kb/stores.json","w"),indent=1); print(json.dumps(d,indent=1))'
$KB stores list
