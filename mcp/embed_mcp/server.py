"""
embed-mcp — MCP server exposing an EMBEd vault to MCP-aware LLM clients.

Thin HTTP proxy: each tool calls a running EMBEd backend (default
http://localhost:8000) and returns shaped JSON.

Per-vault API keys are read from a JSON file (default
~/.config/embed-mcp/keys.json). Optional "admin" entry unlocks
admin-only endpoints (e.g. list_vaults).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP


BASE_URL = os.environ.get("EMBED_BASE_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = float(os.environ.get("EMBED_TIMEOUT", "30"))
KEYS_PATH = Path(
    os.environ.get("EMBED_MCP_KEYS")
    or (Path.home() / ".config" / "embed-mcp" / "keys.json")
)

mcp = FastMCP("embed")


def _load_keys() -> dict[str, str]:
    if not KEYS_PATH.exists():
        return {}
    try:
        with KEYS_PATH.open() as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception:
        pass
    return {}


def _client() -> httpx.Client:
    return httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)


def _missing_key(vault: str) -> dict[str, Any]:
    return {
        "error": f"no API key for vault '{vault}'",
        "fix": f"add an entry for '{vault}' in {KEYS_PATH}",
    }


@mcp.tool()
def health() -> dict[str, Any]:
    """Backend health (liveness, model readiness, memory). No auth required."""
    with _client() as c:
        r = c.get("/api/health")
    return r.json()


@mcp.tool()
def list_vaults() -> dict[str, Any]:
    """List all vaults on the connected EMBEd backend.

    Reports which vaults have a saved API key locally; vaults without a
    saved key appear in `missing_keys` (search/embed against them will
    fail until you add the key to keys.json). Requires the admin key
    (saved under the name "admin" in keys.json) when ADMIN_API_KEY is
    set on the backend.
    """
    keys = _load_keys()
    headers = {"X-API-Key": keys["admin"]} if "admin" in keys else {}
    with _client() as c:
        r = c.get("/api/stores", headers=headers)
    if r.status_code == 401:
        return {
            "error": "admin auth required",
            "fix": f"add an 'admin' entry to {KEYS_PATH}",
        }
    if r.status_code != 200:
        return {"error": r.text, "status": r.status_code}

    data = r.json()
    stores = data.get("stores", [])
    missing = []
    for s in stores:
        s["has_api_key"] = s["name"] in keys
        if s["name"] not in keys:
            missing.append(s["name"])
    return {"vaults": stores, "total": len(stores), "missing_keys": missing}


@mcp.tool()
def search_vault(vault: str, query: str, n_results: int = 5) -> dict[str, Any]:
    """Search a vault by text query. Returns top-N hits with text, source, similarity.

    Args:
        vault: name of the vault to search
        query: natural-language query
        n_results: max results to return (default 5)
    """
    key = _load_keys().get(vault)
    if not key:
        return _missing_key(vault)
    with _client() as c:
        r = c.post(
            "/api/search",
            headers={"X-API-Key": key},
            data={
                "vector_store": vault,
                "query": query,
                "n_results": str(n_results),
            },
        )
    if r.status_code != 200:
        return {"error": r.text, "status": r.status_code}

    j = r.json()
    out = []
    for hit in j.get("results", []):
        meta = hit.get("metadata", {})
        item = {
            "text": hit.get("document", ""),
            "source_file": meta.get("filename"),
            "similarity": hit.get("similarity"),
            "modality": meta.get("modality"),
            "file_url": meta.get("file_url"),
        }
        if "page_numbers" in meta:
            item["page_numbers"] = meta["page_numbers"]
        out.append(item)
    return {"vault": vault, "query": query, "count": len(out), "results": out}


@mcp.tool()
def embed_into_vault(vault: str, text: str) -> dict[str, Any]:
    """Embed a string of text into a vault.

    Args:
        vault: name of the vault
        text: raw text to embed (will be chunked if longer than chunk_size)
    """
    key = _load_keys().get(vault)
    if not key:
        return _missing_key(vault)
    with _client() as c:
        r = c.post(
            "/api/embed",
            headers={"X-API-Key": key},
            data={"vector_store": vault, "text": text},
        )
    if r.status_code != 200:
        return {"error": r.text, "status": r.status_code}

    j = r.json()
    return {
        "doc_id": j.get("id"),
        "chunk_count": j.get("chunks"),
        "vault": j.get("store"),
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
