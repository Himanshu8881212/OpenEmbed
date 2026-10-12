#!/usr/bin/env python3
"""Minimal multimodal RAG over a Knowledge Store (standard library only).

Retrieval: the store's search API (the service embeds the query with EmbeddingGemma 2 and returns source-linked
evidence). Generation: your own answer model, here a local Ollama model (default gemma4:12b-nvfp4). Retrieved images
are passed to the model as pictures; text passages are passed with [n] citations.

  export KNOWLEDGE_API_KEY=kb_...            # search (+ source:read to show retrieved images to the model)
  python3 examples/dune/rag.py --store dune-bags "How many ribs does the Mirage bag have?"
  python3 examples/dune/rag.py --store dune-bags --image "~/Downloads/DUNE Bags/Sahara - quilted charm bag/Sahara_01_hero.png" "Which bag is this?"
  python3 examples/dune/rag.py --selftest     # end-to-end checks across all demo stores
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("KB_BASE_URL", "http://localhost:3000")
OLLAMA = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("RAG_MODEL", "gemma4:12b-nvfp4")
HERE = os.path.dirname(os.path.abspath(__file__))


def key() -> str:
    k = os.environ.get("KNOWLEDGE_API_KEY") or open(os.path.join(HERE, ".kb", "app.key")).read().strip()
    return k


def http(method: str, url: str, body=None, raw: bytes | None = None, headers: dict | None = None, timeout=300):
    h = {"authorization": f"Bearer {key()}", **(headers or {})} if url.startswith(BASE) else dict(headers or {})
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    if body is not None:
        h["content-type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ct = r.headers.get("content-type", "")
            payload = r.read()
            return json.loads(payload) if "json" in ct else payload
    except urllib.error.HTTPError as e:
        err = e.read().decode(errors="replace")
        raise SystemExit(f"{method} {url} -> {e.code}: {err}")


def store_id(name_or_id: str) -> str:
    stores = json.load(open(os.path.join(HERE, ".kb", "stores.json"))) if os.path.exists(os.path.join(HERE, ".kb", "stores.json")) else {}
    return stores.get(name_or_id, name_or_id)


def where(loc: dict) -> str:
    if "start_seconds" in loc:
        return f"{loc['start_seconds']:.0f}-{loc['end_seconds']:.0f}s"
    if "page" in loc:
        return f"page {loc['page']}"
    if "start" in loc:
        return (f"section '{loc['section']}', " if loc.get("section") else "") + f"chars {loc['start']}-{loc['end']}"
    return "whole image"


def retrieve(store: str, question: str | None, image: str | None, k: int) -> dict:
    query = {}
    if question:
        query["text"] = question
    asset = None
    if image:
        path = os.path.expanduser(image)
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        asset = http("POST", f"{BASE}/v1/query-assets", raw=open(path, "rb").read(), headers={"content-type": ctype})["id"]
        query["asset_id"] = asset
    try:
        return http("POST", f"{BASE}/v1/stores/{store_id(store)}/search", {"query": query, "limit": k})
    finally:
        if asset:
            http("DELETE", f"{BASE}/v1/query-assets/{asset}")


def answer(question: str, hits: dict, max_images: int = 2, query_image: str | None = None) -> str:
    context, images = [], []
    if query_image:  # the user's picture is part of the question: show it to the answer model first
        images.append(base64.b64encode(open(os.path.expanduser(query_image), "rb").read()).decode())
        context.append("[query image] attached as image 1. The numbered sources below are the store's closest matches to it.")
    for n, r in enumerate(hits["results"], 1):
        src = r["source"]
        label = f"[{n}] {src['path']} ({where(src['location'])})"
        if isinstance(r["content"], str):
            context.append(f"{label}\n{r['content']}")
        else:
            context.append(f"{label}\n<{r['content']['type']} segment from this file>")
            if r["content"]["type"] == "image" and len(images) < max_images + (1 if query_image else 0):
                try:  # needs source:read; the model then sees the actual picture
                    images.append(base64.b64encode(http("GET", f"{BASE}/v1/files/{src['file_id']}/content?version_id={src['version_id']}")).decode())
                    context[-1] += f" (attached as image {len(images)})"
                except SystemExit:
                    pass
    system = ("You answer questions about a product catalogue using ONLY the numbered context. Cite sources like [1]. "
              "File paths name the product (bag) each source belongs to. When a query image is given, identify it by comparing it "
              "with the attached matches and their file paths. If the context does not contain the answer, say "
              "'Not found in this store.' Be concise.")
    msg = {"role": "user", "content": "Context:\n\n" + "\n\n".join(context) + f"\n\nQuestion: {question}"}
    if images:
        msg["images"] = images
    r = http("POST", f"{OLLAMA}/api/chat", {"model": MODEL, "stream": False, "options": {"temperature": 0}, "think": False,
                                            "messages": [{"role": "system", "content": system}, msg]}, timeout=600)
    return r["message"]["content"].strip()


def ask(store: str, question: str, image: str | None = None, k: int = 6, show=True):
    hits = retrieve(store, question, image, k)
    text = answer(question or "Which product is shown in the query image?", hits, query_image=image) if hits["results"] else "Not found in this store."
    if show:
        print(f"\n### [{store}] {question or ''}{' + image ' + os.path.basename(image) if image else ''}\n{text}\n")
        for n, r in enumerate(hits["results"], 1):
            print(f"  [{n}] {r['score']:.3f}  {r['source']['path']}  ({where(r['source']['location'])})")
    return text, hits


def selftest() -> int:
    """End-to-end checks: retrieval scope per store shape + grounded answers from the real answer model."""
    D = os.path.expanduser("~/Downloads/DUNE Bags")
    bags = lambda hits: {r["source"]["path"].split(" - ")[0] for r in hits["results"]}
    checks = []

    def check(name, ok, detail=""):
        checks.append(ok)
        print(f"{'PASS' if ok else 'FAIL'}  {name}{('  — ' + detail) if detail and not ok else ''}")

    # 1. base store: facts from each bag's info sheet
    for store, q, bag, must in [
        ("dune-bags", "How many vertical ribs does the Mirage bag have?", "Mirage", ["192"]),
        ("dune-bags", "How many quilted diamonds does the Sahara bag have, and how far do the pillows dome out?", "Sahara", ["16", "0.7"]),
        ("dune-bags", "How much does the Sirocco bag weigh when printed solid in TPU?", "Sirocco", ["301"]),
    ]:
        text, hits = ask(store, q)
        check(f"base store retrieves {bag} sheet first", hits["results"][0]["source"]["path"].startswith(bag), str(bags(hits)))
        check(f"answer for {bag} contains {must}", all(m in text for m in must), text[:200])
    # 2. cross-document reasoning over the base store
    text, _ = ask("dune-bags", "Which of the bags have charm holes, and which one has none?", k=8)
    check("cross-document: Sirocco has no charm holes", "Sirocco" in text and ("Mirage" in text or "Sahara" in text), text[:200])
    # 3. split stores only contain their own bag
    for bag in ["Sirocco", "Mirage", "Sahara"]:
        _, hits = ask(f"dune-{bag.lower()}", "wall thickness and weight of the bag", show=False)
        check(f"split store dune-{bag.lower()} only returns {bag}", bags(hits) == {bag}, str(bags(hits)))
    # 4. merged store = Sirocco + Mirage, never Sahara
    text, hits = ask("dune-sirocco-mirage", "Describe the quilted diamond pattern of the Sahara bag.", k=6)
    check("merged store excludes Sahara sources", "Sahara" not in bags(hits), str(bags(hits)))
    check("answer model says it is not in the merged store", "not found" in text.lower() or "does not" in text.lower() or "no information" in text.lower(), text[:200])
    _, hits = ask("dune-sirocco-mirage", "TPU weight of the bags", k=10, show=False)
    check("merged store contains both Sirocco and Mirage", {"Sirocco", "Mirage"} <= bags(hits), str(bags(hits)))
    # 5. snapshot of info sheets: documents only
    _, hits = ask("dune-info-sheets", "print settings and supports", k=5, show=False)
    check("snapshot holds only the three info sheets", all(r["source"]["path"].endswith("_info.docx") for r in hits["results"]) and len({r["source"]["file_id"] for r in hits["results"]}) <= 3)
    # 6. nested view: Sahara renders only
    _, hits = ask("dune-sahara-renders", "studio product photo", k=10, show=False)
    check("nested view = Sahara studio renders only", bool(hits["results"]) and all(r["source"]["path"].startswith("Sahara") and "/frames/" not in r["source"]["path"] and r["source"]["path"].endswith(".png") for r in hits["results"]), str([r["source"]["path"] for r in hits["results"]][:4]))
    # 7. multimodal: image query finds the right bag; the answer model names it from the retrieved pictures
    text, hits = ask("dune-bags", "Which DUNE bag is shown in this picture?", image=f"{D}/Sahara - quilted charm bag/Sahara_01_hero.png", k=6)
    top = [r["source"]["path"].split(" - ")[0] for r in hits["results"][:3]]
    check("image query: top results are Sahara", top.count("Sahara") >= 2, str(top))
    check("answer names Sahara", "Sahara" in text, text[:200])
    _, hits = ask("dune-bags", "turntable video of the draped satin bag", k=10, show=False)
    check("video segments are retrievable", any(r["source"]["path"].endswith(".mp4") for r in hits["results"]), str([r["source"]["path"] for r in hits["results"]][:5]))
    print(f"\n{sum(checks)}/{len(checks)} checks passed", flush=True)
    return 0 if all(checks) else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("question", nargs="?")
    ap.add_argument("--store", default="dune-bags")
    ap.add_argument("--image")
    ap.add_argument("-k", type=int, default=6)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    if not a.question and not a.image:
        ap.error("ask a question and/or pass --image")
    ask(a.store, a.question, a.image, a.k)
