#!/usr/bin/env python3
"""Passage-level retrieval quality on the DUNE info sheets (long, sectioned, with tables).

Metric (predeclared): answer@1 / answer@3 = share of questions whose expected fact string appears in the top-1 / top-3
retrieved passages. Sensitive to chunk boundaries, unlike file-level hit@k. Usage:
  python3 examples/dune/eval_chunking.py [--store dune-bags] [--mode hybrid|vector]
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
QA = [
    ("What is the minimum centre-to-centre spacing between charm holes on the Mirage bag?", "Mirage", "25 mm"),
    ("Which printer bed is borderline for the Sahara bag?", "Sahara", "Prusa MK4"),
    ("How deep are the ribs on the Mirage bag?", "Mirage", "0.5 mm"),
    ("What is the wall thickness of the Sirocco body?", "Sirocco", "2.4 mm"),
    ("How many triangles are in the Sirocco mesh?", "Sirocco", "992,454"),
    ("How wide are the quilt seams on the Sahara bag?", "Sahara", "2.6 mm"),
    ("What size are the strap slots on the Mirage bag?", "Mirage", "16 x 6"),
    ("How narrow is the top opening of the Sirocco bag?", "Sirocco", "33 mm"),
    ("Does the Sirocco bag need supports when printing?", "Sirocco", "NO"),
    ("How much does the Mirage bag weigh in TPU?", "Mirage", "252 g"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default="dune-bags")
    ap.add_argument("--mode", default="hybrid")
    a = ap.parse_args()
    key = open(os.path.join(HERE, ".kb", "app.key")).read().strip()
    sid = json.load(open(os.path.join(HERE, ".kb", "stores.json")))[a.store]
    at1 = at3 = 0
    profile = None
    for q, bag, fact in QA:
        req = urllib.request.Request(f"http://localhost:3000/v1/stores/{sid}/search", method="POST",
                                     data=json.dumps({"query": {"text": q}, "limit": 3, "mode": a.mode, "modalities": ["text"]}).encode(),
                                     headers={"authorization": f"Bearer {key}", "content-type": "application/json"})
        r = json.load(urllib.request.urlopen(req))
        profile = r["profile_id"]
        passages = [x["content"] for x in r["results"] if x["source"]["path"].startswith(bag)]
        top = r["results"][0] if r["results"] else None
        ok1 = bool(top) and top["source"]["path"].startswith(bag) and fact in top["content"]
        ok3 = any(fact in p for p in passages)
        at1 += ok1
        at3 += ok3
        if not ok3:
            print(f"  miss: {q}  (expected '{fact}')")
    n = len(QA)
    print(json.dumps({"profile": profile, "mode": a.mode, "answer@1": round(at1 / n, 3), "answer@3": round(at3 / n, 3), "n": n}))


if __name__ == "__main__":
    main()
