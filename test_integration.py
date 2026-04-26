#!/usr/bin/env python3
"""
End-to-end integration test for EMBEd.

Verifies that all three connect paths advertised in the UI work:
    1. curl     — shells out to /usr/bin/curl
    2. python   — uses httpx directly
    3. MCP      — imports embed_mcp.server and calls each @mcp.tool

Run with the backend already up:

    python -m app.main          # in one terminal
    python test_integration.py  # in another

Optional env:
    EMBED_BASE_URL  default http://localhost:8000
    ADMIN_API_KEY   if backend was started with one — required for /stores admin ops
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import httpx


BASE_URL = os.environ.get("EMBED_BASE_URL", "http://localhost:8000").rstrip("/")
ADMIN_KEY = os.environ.get("ADMIN_API_KEY", "")
VAULT = f"itest-{uuid.uuid4().hex[:8]}"

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
RESET = "\033[0m"

passed = 0
failed = 0


def step(name: str) -> None:
    print(f"\n{YELLOW}── {name} ──{RESET}")


def ok(msg: str) -> None:
    global passed
    passed += 1
    print(f"  {GREEN}PASS{RESET}  {msg}")


def fail(msg: str) -> None:
    global failed
    failed += 1
    print(f"  {RED}FAIL{RESET}  {msg}")


def die(msg: str) -> None:
    print(f"\n{RED}ABORT{RESET}  {msg}")
    sys.exit(1)


def admin_headers() -> dict[str, str]:
    return {"X-API-Key": ADMIN_KEY} if ADMIN_KEY else {}


# ── 1. preflight ────────────────────────────────────────────────────

def preflight() -> dict:
    step("preflight: backend reachable?")
    try:
        r = httpx.get(f"{BASE_URL}/api/health", timeout=5)
    except httpx.HTTPError as e:
        die(f"cannot reach {BASE_URL}: {e}\nstart the backend with `python -m app.main`")

    if r.status_code != 200:
        die(f"/api/health returned {r.status_code}")

    health = r.json()
    ok(f"backend up — status={health.get('status')}")
    if not health.get("perception_encoder"):
        print(f"  {DIM}note: perception encoder not ready — embed/search will fail{RESET}")
    return health


# ── 2. create + key issuance ────────────────────────────────────────

def create_vault() -> str:
    step(f"create vault '{VAULT}' (admin)")
    with httpx.Client(timeout=30) as c:
        r = c.post(
            f"{BASE_URL}/api/stores",
            headers=admin_headers(),
            data={"name": VAULT, "description": "integration test vault"},
        )
    if r.status_code == 401:
        die("admin key required — re-run with ADMIN_API_KEY=...")
    if r.status_code != 200:
        die(f"create_store failed: {r.status_code} {r.text}")
    j = r.json()
    api_key = j.get("api_key")
    if not (api_key and api_key.startswith("sk-embed-")):
        die(f"no api_key in response: {j}")
    ok(f"vault created, api_key={api_key[:18]}…")
    return api_key


def delete_vault(vault_key: str) -> None:
    step(f"cleanup: delete vault '{VAULT}'")
    headers = admin_headers() or {"X-API-Key": vault_key}
    with httpx.Client(timeout=30) as c:
        r = c.delete(f"{BASE_URL}/api/stores/{VAULT}", headers=headers)
    if r.status_code == 200:
        ok("vault deleted")
    else:
        fail(f"delete returned {r.status_code} {r.text}")


# ── 3. curl path ────────────────────────────────────────────────────

def curl_test(vault_key: str) -> None:
    step("curl path")
    if not shutil.which("curl"):
        fail("curl not installed — skipping")
        return

    # 3a. embed text via curl
    cmd = [
        "curl", "-sS", "-X", "POST", f"{BASE_URL}/api/embed",
        "-H", f"X-API-Key: {vault_key}",
        "-F", f"vector_store={VAULT}",
        "-F", "text=The Eiffel Tower is in Paris and stands 330 metres tall.",
    ]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        fail(f"curl embed exited {out.returncode}: {out.stderr.strip()}")
        return
    try:
        j = json.loads(out.stdout)
    except Exception:
        fail(f"curl embed: not JSON: {out.stdout[:200]}")
        return
    if not j.get("success"):
        fail(f"curl embed: {j}")
        return
    ok(f"curl embed → doc_id={j['id'][:8]}… chunks={j['chunks']}")

    # 3b. search via curl
    cmd = [
        "curl", "-sS", "-X", "POST", f"{BASE_URL}/api/search",
        "-H", f"X-API-Key: {vault_key}",
        "-F", f"vector_store={VAULT}",
        "-F", "query=where is the eiffel tower",
        "-F", "n_results=3",
    ]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        fail(f"curl search exited {out.returncode}: {out.stderr.strip()}")
        return
    j = json.loads(out.stdout)
    hits = j.get("results", [])
    if not hits:
        fail(f"curl search returned 0 hits: {j}")
        return
    ok(f"curl search → {len(hits)} hits, top similarity={hits[0].get('similarity'):.3f}")


# ── 4. python (httpx) path ──────────────────────────────────────────

def python_test(vault_key: str) -> None:
    step("python (httpx) path")
    with httpx.Client(timeout=30) as c:
        # 4a. embed text
        r = c.post(
            f"{BASE_URL}/api/embed",
            headers={"X-API-Key": vault_key},
            data={
                "vector_store": VAULT,
                "text": "Mount Everest is the tallest mountain on Earth at 8849 metres.",
            },
        )
        if r.status_code != 200:
            fail(f"python embed: {r.status_code} {r.text}")
            return
        j = r.json()
        ok(f"python embed → doc_id={j['id'][:8]}… chunks={j['chunks']}")

        # 4b. search
        r = c.post(
            f"{BASE_URL}/api/search",
            headers={"X-API-Key": vault_key},
            data={
                "vector_store": VAULT,
                "query": "tallest mountain",
                "n_results": "3",
            },
        )
        if r.status_code != 200:
            fail(f"python search: {r.status_code} {r.text}")
            return
        j = r.json()
        hits = j.get("results", [])
        if not hits:
            fail(f"python search returned 0 hits: {j}")
            return
        ok(f"python search → {len(hits)} hits, top similarity={hits[0].get('similarity'):.3f}")

        # 4c. /retrieve (RAG-shaped)
        r = c.post(
            f"{BASE_URL}/api/retrieve",
            headers={"X-API-Key": vault_key, "Content-Type": "application/json"},
            json={"store": VAULT, "query": "Paris", "top_k": 2},
        )
        if r.status_code != 200:
            fail(f"python retrieve: {r.status_code} {r.text}")
            return
        ctx = r.json().get("context", [])
        if not ctx:
            fail(f"python retrieve returned 0 context items: {r.json()}")
            return
        ok(f"python retrieve → {len(ctx)} context items, top source={ctx[0].get('source')}")


# ── 5. MCP path (in-process import) ─────────────────────────────────

def mcp_test(vault_key: str) -> None:
    step("MCP path (in-process)")

    # Set up keys file at a temp location so we don't clobber the user's real one.
    tmpdir = Path(tempfile.mkdtemp(prefix="embed-mcp-test-"))
    keys_file = tmpdir / "keys.json"
    keys = {VAULT: vault_key}
    if ADMIN_KEY:
        keys["admin"] = ADMIN_KEY
    keys_file.write_text(json.dumps(keys))

    os.environ["EMBED_BASE_URL"] = BASE_URL
    os.environ["EMBED_MCP_KEYS"] = str(keys_file)

    # Make sure the freshly-installed mcp/ is importable
    mcp_path = str(Path(__file__).parent / "mcp")
    if mcp_path not in sys.path:
        sys.path.insert(0, mcp_path)

    # Force a fresh import so module-level constants pick up our env vars
    for m in [k for k in list(sys.modules) if k.startswith("embed_mcp")]:
        del sys.modules[m]
    try:
        from embed_mcp import server as mcp_server
    except Exception as e:
        fail(f"could not import embed_mcp.server: {e}")
        shutil.rmtree(tmpdir, ignore_errors=True)
        return

    # 5a. health tool
    h = mcp_server.health()
    if not isinstance(h, dict) or "status" not in h:
        fail(f"mcp health: unexpected payload {h}")
    else:
        ok(f"mcp health → status={h['status']}")

    # 5b. embed_into_vault
    res = mcp_server.embed_into_vault(
        vault=VAULT,
        text="The Pacific Ocean is the largest ocean on Earth.",
    )
    if "error" in res:
        fail(f"mcp embed_into_vault: {res}")
    else:
        ok(f"mcp embed_into_vault → doc_id={res['doc_id'][:8]}… chunks={res['chunk_count']}")

    # 5c. search_vault
    res = mcp_server.search_vault(vault=VAULT, query="largest ocean", n_results=3)
    if "error" in res or not res.get("results"):
        fail(f"mcp search_vault: {res}")
    else:
        top = res["results"][0]
        ok(f"mcp search_vault → {res['count']} hits, top sim={top['similarity']:.3f}")

    # 5d. list_vaults (only meaningful when admin key is configured)
    res = mcp_server.list_vaults()
    if "error" in res:
        # In dev mode with no ADMIN_API_KEY this still works (server returns 200).
        # The error path is only hit when backend enforces admin auth.
        print(f"  {DIM}list_vaults: {res['error']} (set ADMIN_API_KEY + 'admin' key to test){RESET}")
    elif VAULT in [v.get("name") for v in res.get("vaults", [])]:
        ok(f"mcp list_vaults → {len(res['vaults'])} vaults, includes '{VAULT}'")
    else:
        fail(f"mcp list_vaults missing test vault: {res}")

    shutil.rmtree(tmpdir, ignore_errors=True)


# ── main ─────────────────────────────────────────────────────────────

def main() -> int:
    print(f"{DIM}EMBEd integration test{RESET}")
    print(f"{DIM}base url: {BASE_URL}{RESET}")
    print(f"{DIM}admin key: {'set' if ADMIN_KEY else 'unset (dev mode)'}{RESET}")

    preflight()
    vault_key = create_vault()

    # Give Chroma a moment to register the new collection before traffic hits it
    time.sleep(0.2)

    try:
        curl_test(vault_key)
        python_test(vault_key)
        mcp_test(vault_key)
    finally:
        delete_vault(vault_key)

    print()
    if failed == 0:
        print(f"{GREEN}all good — {passed} checks passed{RESET}")
        return 0
    print(f"{RED}{failed} failed, {passed} passed{RESET}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
