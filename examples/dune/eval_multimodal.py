#!/usr/bin/env python3
"""Cross-modal retrieval check on DUNE Bags: does the right bag come first? (text→image/video, image→text/video/image)
Descriptions avoid product names. Usage: python3 examples/dune/eval_multimodal.py [--store dune-bags]"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.expanduser("~/Downloads/DUNE Bags")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default="dune-bags")
    a = ap.parse_args()
    K = open(os.path.join(HERE, ".kb", "app.key")).read().strip()
    S = json.load(open(os.path.join(HERE, ".kb", "stores.json")))[a.store]

    def call(m, p, body=None, raw=None, ctype=None):
        h = {"authorization": f"Bearer {K}"}
        if body is not None:
            h["content-type"] = "application/json"
            raw = json.dumps(body).encode()
        if ctype:
            h["content-type"] = ctype
        r = urllib.request.urlopen(urllib.request.Request("http://localhost:3000" + p, data=raw, method=m, headers=h))
        return json.load(r) if r.status != 204 else None

    def search(query, mods, k=5):
        return call("POST", f"/v1/stores/{S}/search", {"query": query, "limit": k, "modalities": mods, "mode": "vector"})["results"]

    bag = lambda r: r["source"]["path"].split(" - ")[0]
    videos = {p.split(" - ")[0] for p in os.listdir(D) if os.path.isdir(os.path.join(D, p)) for f in os.listdir(os.path.join(D, p)) if f.endswith(".mp4")}
    rows = []
    for q, want in [("a bag whose surface is a quilt of puffy diamonds", "Sahara"), ("a bag covered in fine vertical ribs", "Mirage"),
                    ("a bag with soft draped satin folds", "Sirocco"), ("a bag shaped like flower petals", "Petal")]:
        for mod in ["image", "video"]:
            if mod == "video" and want not in videos:
                continue  # no video of this bag exists: not applicable
            top = [bag(r) for r in search({"text": q}, [mod])]
            rows.append((f"text→{mod}", q[:44], want, top[0] if top else "-"))
    for b, f in [("Sahara", "Sahara - quilted charm bag/Sahara_02_front.png"), ("Mirage", "Mirage - ribbed charm bag/Mirage_02_front.png"), ("Sirocco", "Sirocco - draped satin/Sirocco_02_front.png")]:
        aid = call("POST", "/v1/query-assets", raw=open(f"{D}/{f}", "rb").read(), ctype="image/png")["id"]
        for mod in ["text", "video", "image"]:
            top = [bag(r) for r in search({"asset_id": aid}, [mod], 6) if r["source"]["path"] != f][:5]
            rows.append((f"image→{mod}", f.split("/")[1], b, top[0] if top else "-"))
        call("DELETE", f"/v1/query-assets/{aid}")
    for r in rows:
        print(f"{'✓' if r[2] == r[3] else '✗'} {r[0]:13} {r[1]:46} want {r[2]:8} top1 {r[3]}")
    prof = call("GET", f"/v1/stores/{S}")["profile_id"]
    print(json.dumps({"profile": prof, "top1_correct": sum(r[2] == r[3] for r in rows), "n": len(rows)}))


if __name__ == "__main__":
    main()
