#!/usr/bin/env python3
"""
Retrieval evaluation harness.

Builds a small gold-labeled corpus, fires a battery of deliberately hard
queries against the live backend, and scores the results on:

  Hit@K       did the gold doc land in top-K?
  Rank        position of the first gold doc (1-best)
  Precision   fraction of top-K results that are relevant
  Reject      for out-of-domain queries: did the system return 0 hits?

Each query is tagged with a difficulty class so you can see *where* the
system is strong vs weak — not just an aggregate score.

Run:
    python scripts/eval.py            # default endpoint
    EMBED_BASE_URL=https://...  python scripts/eval.py
"""
from __future__ import annotations
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import List, Set, Optional

import httpx


BASE = os.environ.get("EMBED_BASE_URL", "http://localhost:8000").rstrip("/")
ADMIN_KEY = os.environ.get("ADMIN_API_KEY", "")
TOP_K = 5
RERANK_FLOOR = -5.0  # tuned: leaves room for paraphrase (-3..-4) above junk (~-10)


# ── ANSI ─────────────────────────────────────────────────────────
G = "\033[32m"; R = "\033[31m"; Y = "\033[33m"
DIM = "\033[2m"; B = "\033[1m"; RESET = "\033[0m"


# ── Corpus ───────────────────────────────────────────────────────
# Each doc has a stable id used to score retrieval. Topics deliberately
# overlap so plausible-but-wrong distractors exist for several queries.

@dataclass
class Doc:
    id: str
    text: str


CORPUS: List[Doc] = [
    Doc("eiffel",      "The Eiffel Tower in Paris was completed in 1889 for the Exposition Universelle. It stands 330 metres tall and is built from puddled iron."),
    Doc("liberty",     "The Statue of Liberty was a gift from France to the United States, dedicated in 1886 on Liberty Island in New York Harbor. Its outer skin is copper."),
    Doc("everest",     "Mount Everest at 8,849 metres is the highest peak in the Himalayan range, on the border of Nepal and China."),
    Doc("k2",          "K2 is the second-highest mountain on Earth at 8,611 metres, located in the Karakoram range on the China-Pakistan border."),
    Doc("mariana",     "The Mariana Trench in the Pacific Ocean reaches a depth of 10,994 metres at the Challenger Deep, the deepest known point on Earth."),
    Doc("octopus",     "Octopuses have three hearts, blue copper-based blood, and nine brains — one central plus one in each arm."),
    Doc("sharks",      "Sharks predate trees by more than 100 million years; they have inhabited Earth for over 400 million years."),
    Doc("photo",       "Photosynthesis converts solar energy into chemical energy stored in glucose, releasing oxygen as a byproduct."),
    Doc("quantum",     "Quantum entanglement describes correlated quantum states between particles regardless of separation distance."),
    Doc("apollo",      "The Apollo 11 mission landed Neil Armstrong and Buzz Aldrin on the Moon on July 20, 1969."),
    Doc("kestrel_q3",  "Project KESTREL-7 missed its Q3 milestone by 14 days; root cause was the upstream FOO-882 dependency stalling in QA."),
    Doc("kestrel_q4",  "Project KESTREL-7's Q4 plan focuses on the FOO-882 retry path. Owner: Yuki Tanaka. Estimated unblock: late November."),
    Doc("yuki",        "Yuki Tanaka leads three projects: KESTREL-7, BLAZER-3, and the FOO-882 platform stabilization effort."),
    Doc("python_gil",  "CPython's Global Interpreter Lock prevents multiple native threads from executing Python bytecode in parallel."),
    Doc("rust_borrow", "Rust's borrow checker enforces memory safety at compile time without a garbage collector."),
]


# ── Query battery ────────────────────────────────────────────────

@dataclass
class Query:
    q: str
    gold: Set[str]                     # set of doc ids that count as "correct"
    difficulty: str                    # one-line category for grouping
    out_of_domain: bool = False        # should return zero results
    notes: str = ""

QUERIES: List[Query] = [
    # Easy / lexical
    Query("Eiffel Tower",                          {"eiffel"},               "lexical exact"),
    Query("Apollo 11 moon landing",                {"apollo"},               "lexical exact"),

    # Paraphrase / synonym
    Query("the world's tallest peak",              {"everest"},              "paraphrase",  notes="doc says 'highest', query says 'tallest'"),
    Query("blood color of cephalopods",            {"octopus"},              "paraphrase",  notes="doc says 'blue', no 'cephalopod' token"),
    Query("how plants make food from sunlight",    {"photo"},                "paraphrase"),

    # Distractor heavy
    Query("iron monument completed in the 1880s",  {"eiffel"},               "distractor",  notes="liberty also 1880s but copper"),
    Query("French gift to America",                {"liberty"},              "distractor",  notes="eiffel also French"),
    Query("second-highest mountain",               {"k2"},                   "distractor",  notes="everest is taller, K2 is second"),

    # Specific entity / BM25 wins
    Query("FOO-882",                               {"kestrel_q3", "kestrel_q4", "yuki"}, "rare entity"),
    Query("KESTREL-7 Q4 owner",                    {"kestrel_q4"},           "rare entity + paraphrase"),

    # Multi-hop reasoning
    Query("who runs the project that missed Q3",   {"kestrel_q3", "kestrel_q4", "yuki"}, "multi-hop", notes="needs 2-3 chunks chained"),
    Query("which project does Yuki lead besides KESTREL-7 and BLAZER-3", {"yuki"}, "multi-hop"),

    # Inference / general knowledge in vault
    Query("the deepest known point on Earth",      {"mariana"},              "inference"),

    # Niche technical
    Query("why CPython doesn't have true threading", {"python_gil"},         "technical paraphrase"),
    Query("memory safety without garbage collection", {"rust_borrow"},       "technical paraphrase"),

    # Out-of-domain — system MUST return nothing
    Query("best Italian restaurant in Brooklyn",   set(),                    "out-of-domain", out_of_domain=True),
    Query("how to bake sourdough bread",           set(),                    "out-of-domain", out_of_domain=True),
    Query("asdfgh qwerty zzzz",                    set(),                    "nonsense",      out_of_domain=True),
]


# ── Scoring ──────────────────────────────────────────────────────

@dataclass
class Result:
    query: Query
    hits: List[str]            # doc ids of returned chunks
    rerank_scores: List[float]
    rank: Optional[int] = None # 1-based position of first gold; None if missed
    hit_at_k: bool = False
    precision_at_k: float = 0.0
    correctly_rejected: bool = False


def score_query(q: Query, returned: List[dict]) -> Result:
    # Each `returned` item has `metadata.filename` shaped like `<docid>.txt`
    # because we embed text via /api/embed?text=... → filename is "text_input".
    # We instead encode the doc id in the embed text prefix; see run_eval.
    hits = []
    for r in returned[:TOP_K]:
        meta = r.get("metadata", {})
        # We tag each doc with its id at the start of the chunk text.
        text = r.get("document", "") or ""
        marker = text[:32]
        if marker.startswith("[[") and "]]" in marker:
            doc_id = marker[2:marker.index("]]")]
            hits.append(doc_id)
        else:
            hits.append(meta.get("filename") or "?")

    rerank_scores = [r.get("rerank_score") for r in returned[:TOP_K]]

    rank = None
    for i, h in enumerate(hits, 1):
        if h in q.gold:
            rank = i
            break
    relevant_count = sum(1 for h in hits if h in q.gold)
    precision_at_k = relevant_count / max(1, len(hits))
    hit_at_k = rank is not None

    correctly_rejected = q.out_of_domain and len(returned) == 0

    return Result(
        query=q,
        hits=hits,
        rerank_scores=rerank_scores,
        rank=rank,
        hit_at_k=hit_at_k,
        precision_at_k=precision_at_k,
        correctly_rejected=correctly_rejected,
    )


# ── Driver ───────────────────────────────────────────────────────

def admin_headers() -> dict:
    return {"X-API-Key": ADMIN_KEY} if ADMIN_KEY else {}


def run_eval() -> int:
    print(f"{B}Retrieval evaluation{RESET}")
    print(f"{DIM}base: {BASE}  top_k={TOP_K}  rerank_floor={RERANK_FLOOR}{RESET}\n")

    # 1. probe backend
    try:
        r = httpx.get(f"{BASE}/api/health", timeout=5)
    except httpx.HTTPError as e:
        print(f"{R}cannot reach {BASE}: {e}{RESET}")
        return 1
    if r.status_code != 200:
        print(f"{R}/api/health returned {r.status_code}{RESET}")
        return 1
    if not r.json().get("perception_encoder"):
        print(f"{Y}warning: perception encoder not ready{RESET}")

    # 2. fresh vault
    vault = f"eval-{uuid.uuid4().hex[:8]}"
    print(f"{DIM}building vault {vault}…{RESET}")
    with httpx.Client(timeout=120) as c:
        rr = c.post(f"{BASE}/api/stores", headers=admin_headers(),
                    data={"name": vault, "description": "retrieval eval"})
        if rr.status_code != 200:
            print(f"{R}create vault failed: {rr.status_code} {rr.text}{RESET}")
            return 1
        key = rr.json()["api_key"]
        H = {"X-API-Key": key}

        # 3. embed corpus — prefix text with [[id]] so we can recover ids
        for d in CORPUS:
            tagged = f"[[{d.id}]] {d.text}"
            rr = c.post(f"{BASE}/api/embed", headers=H,
                        data={"vector_store": vault, "text": tagged})
            if rr.status_code != 200:
                print(f"{R}embed failed for {d.id}: {rr.status_code} {rr.text[:200]}{RESET}")
                return 1
        print(f"{DIM}embedded {len(CORPUS)} docs{RESET}\n")
        time.sleep(0.3)

        # 4. run queries
        results: List[Result] = []
        for q in QUERIES:
            payload = {"store": vault, "query": q.q, "top_k": TOP_K,
                       "min_rerank_score": RERANK_FLOOR}
            rr = c.post(f"{BASE}/api/retrieve", headers={**H, "Content-Type": "application/json"},
                        json=payload)
            if rr.status_code != 200:
                print(f"{R}/retrieve failed: {rr.status_code} {rr.text[:200]}{RESET}")
                return 1
            ctx = rr.json().get("context", [])
            # /retrieve uses "text" field, /search uses "document". Normalize.
            normalized = [{"document": item.get("text", ""),
                           "metadata": {"filename": item.get("source", "")},
                           "rerank_score": item.get("rerank_score")} for item in ctx]
            results.append(score_query(q, normalized))

        # 5. cleanup
        c.delete(f"{BASE}/api/stores/{vault}", headers=admin_headers() or H)

    # 6. report
    return print_report(results)


def print_report(results: List[Result]) -> int:
    by_diff: dict = {}
    for r in results:
        by_diff.setdefault(r.query.difficulty, []).append(r)

    print(f"{B}Per-query results{RESET}")
    print(f"{DIM}{'difficulty':<28}{'query':<48}{'rank':<6}{'P@K':<6}status{RESET}")
    print("─" * 110)

    for diff in by_diff:
        for r in by_diff[diff]:
            q = r.query
            if q.out_of_domain:
                ok = r.correctly_rejected
                status = f"{G}REJECTED{RESET}" if ok else f"{R}LEAKED ({len(r.hits)} hits){RESET}"
                rank = "—"
                pak = f"{r.precision_at_k:.2f}" if r.hits else "—"
            else:
                ok = r.hit_at_k
                if r.hit_at_k:
                    status = f"{G}hit @ {r.rank}{RESET}"
                else:
                    got = r.hits[:2] if r.hits else ["nothing"]
                    status = f"{R}MISS — got {got}{RESET}"
                rank = str(r.rank) if r.rank else "—"
                pak = f"{r.precision_at_k:.2f}"
            qprint = q.q if len(q.q) <= 46 else q.q[:43] + "…"
            print(f"{diff:<28}{qprint:<48}{rank:<6}{pak:<6}{status}")
        print()

    # Aggregates
    in_domain = [r for r in results if not r.query.out_of_domain]
    ood = [r for r in results if r.query.out_of_domain]

    hit_rate = sum(1 for r in in_domain if r.hit_at_k) / max(1, len(in_domain))
    mrr = sum((1 / r.rank) if r.rank else 0 for r in in_domain) / max(1, len(in_domain))
    avg_pak = sum(r.precision_at_k for r in in_domain) / max(1, len(in_domain))
    reject_rate = sum(1 for r in ood if r.correctly_rejected) / max(1, len(ood))

    print(f"{B}Summary{RESET}")
    print(f"  in-domain queries:          {len(in_domain)}")
    print(f"  Hit@{TOP_K}:                       {hit_rate:.1%}  ({sum(1 for r in in_domain if r.hit_at_k)}/{len(in_domain)})")
    print(f"  MRR (mean reciprocal rank): {mrr:.3f}")
    print(f"  P@{TOP_K} (avg precision):         {avg_pak:.3f}")
    print(f"  out-of-domain queries:      {len(ood)}")
    print(f"  correctly rejected:         {reject_rate:.1%}  ({sum(1 for r in ood if r.correctly_rejected)}/{len(ood)})")

    # By-difficulty breakdown
    print(f"\n{B}By difficulty{RESET}")
    for diff, group in by_diff.items():
        in_d = [r for r in group if not r.query.out_of_domain]
        ood_d = [r for r in group if r.query.out_of_domain]
        if in_d:
            hits = sum(1 for r in in_d if r.hit_at_k)
            print(f"  {diff:<28}  {hits}/{len(in_d)} hits   MRR={sum((1/r.rank) if r.rank else 0 for r in in_d)/len(in_d):.2f}")
        if ood_d:
            rej = sum(1 for r in ood_d if r.correctly_rejected)
            print(f"  {diff:<28}  {rej}/{len(ood_d)} rejected (out-of-domain)")

    # Verdict
    fail = (hit_rate < 0.7) or (reject_rate < 0.7)
    print(f"\n{B}Verdict{RESET}: ", end="")
    if hit_rate >= 0.85 and reject_rate >= 0.85:
        print(f"{G}strong{RESET} — high hit rate and clean rejection")
    elif hit_rate >= 0.7 and reject_rate >= 0.7:
        print(f"{Y}adequate{RESET} — usable, with measurable weak spots above")
    else:
        print(f"{R}weak{RESET} — review failed cases above")

    return 0 if not fail else 1


if __name__ == "__main__":
    sys.exit(run_eval())
