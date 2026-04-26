#!/usr/bin/env python3
"""
End-to-end retrieval evaluation harness.

Sections (run all by default, or pick with --section):
    text      ─ paraphrase, distractor, multi-hop, rare-entity, OOD rejection
    image     ─ cross-modal: text → image, image → image (file query)
    pdf       ─ multi-page PDF: chunk recall, page-tracking
    audio     ─ ASR: text query → speech-bearing audio
    scale     ─ 300 chunks: latency p50/p95, retrieval quality at size

Usage:
    python scripts/eval.py
    python scripts/eval.py --section text
    python scripts/eval.py --section image,pdf
"""
from __future__ import annotations
import argparse
import io
import os
import statistics
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import httpx


BASE = os.environ.get("EMBED_BASE_URL", "http://localhost:8000").rstrip("/")
ADMIN_KEY = os.environ.get("ADMIN_API_KEY", "")
TOP_K = 5
RERANK_FLOOR = -5.0  # tuned: leaves room for paraphrase (-3..-4) above junk (~-10)

G = "\033[32m"; R = "\033[31m"; Y = "\033[33m"
DIM = "\033[2m"; B = "\033[1m"; RESET = "\033[0m"


# ── shared helpers ───────────────────────────────────────────────

def admin_headers() -> dict:
    return {"X-API-Key": ADMIN_KEY} if ADMIN_KEY else {}


def make_vault(c: httpx.Client, prefix: str) -> Tuple[str, str]:
    name = f"{prefix}-{uuid.uuid4().hex[:6]}"
    r = c.post(f"{BASE}/api/stores", headers=admin_headers(),
               data={"name": name, "description": f"eval {prefix}"})
    if r.status_code != 200:
        raise RuntimeError(f"create vault failed: {r.status_code} {r.text}")
    return name, r.json()["api_key"]


def kill_vault(c: httpx.Client, name: str) -> None:
    try:
        c.delete(f"{BASE}/api/stores/{name}", headers=admin_headers(), timeout=15)
    except Exception:
        pass


def bar(label: str) -> None:
    print(f"\n{B}── {label} ──{RESET}")


# ── text section (existing) ──────────────────────────────────────

@dataclass
class Doc:
    id: str
    text: str

@dataclass
class Query:
    q: str
    gold: Set[str]
    difficulty: str
    out_of_domain: bool = False

TEXT_CORPUS: List[Doc] = [
    Doc("eiffel",      "[[eiffel]] The Eiffel Tower in Paris was completed in 1889 for the Exposition Universelle. It stands 330 metres tall and is built from puddled iron."),
    Doc("liberty",     "[[liberty]] The Statue of Liberty was a gift from France to the United States, dedicated in 1886 on Liberty Island in New York Harbor. Its outer skin is copper."),
    Doc("everest",     "[[everest]] Mount Everest at 8,849 metres is the highest peak in the Himalayan range, on the border of Nepal and China."),
    Doc("k2",          "[[k2]] K2 is the second-highest mountain on Earth at 8,611 metres, located in the Karakoram range on the China-Pakistan border."),
    Doc("mariana",     "[[mariana]] The Mariana Trench in the Pacific Ocean reaches a depth of 10,994 metres at the Challenger Deep, the deepest known point on Earth."),
    Doc("octopus",     "[[octopus]] Octopuses have three hearts, blue copper-based blood, and nine brains — one central plus one in each arm."),
    Doc("sharks",      "[[sharks]] Sharks predate trees by more than 100 million years; they have inhabited Earth for over 400 million years."),
    Doc("photo",       "[[photo]] Photosynthesis converts solar energy into chemical energy stored in glucose, releasing oxygen as a byproduct."),
    Doc("quantum",     "[[quantum]] Quantum entanglement describes correlated quantum states between particles regardless of separation distance."),
    Doc("apollo",      "[[apollo]] The Apollo 11 mission landed Neil Armstrong and Buzz Aldrin on the Moon on July 20, 1969."),
    Doc("kestrel_q3",  "[[kestrel_q3]] Project KESTREL-7 missed its Q3 milestone by 14 days; root cause was the upstream FOO-882 dependency stalling in QA."),
    Doc("kestrel_q4",  "[[kestrel_q4]] Project KESTREL-7's Q4 plan focuses on the FOO-882 retry path. Owner: Yuki Tanaka. Estimated unblock: late November."),
    Doc("yuki",        "[[yuki]] Yuki Tanaka leads three projects: KESTREL-7, BLAZER-3, and the FOO-882 platform stabilization effort."),
    Doc("python_gil",  "[[python_gil]] CPython's Global Interpreter Lock prevents multiple native threads from executing Python bytecode in parallel."),
    Doc("rust_borrow", "[[rust_borrow]] Rust's borrow checker enforces memory safety at compile time without a garbage collector."),
]

TEXT_QUERIES: List[Query] = [
    Query("Eiffel Tower",                                                   {"eiffel"},               "lexical exact"),
    Query("Apollo 11 moon landing",                                         {"apollo"},               "lexical exact"),
    Query("the world's tallest peak",                                       {"everest"},              "paraphrase"),
    Query("blood color of cephalopods",                                     {"octopus"},              "paraphrase"),
    Query("how plants make food from sunlight",                             {"photo"},                "paraphrase"),
    Query("iron monument completed in the 1880s",                           {"eiffel"},               "distractor"),
    Query("French gift to America",                                         {"liberty"},              "distractor"),
    Query("second-highest mountain",                                        {"k2"},                   "distractor"),
    Query("FOO-882",                                                        {"kestrel_q3", "kestrel_q4", "yuki"}, "rare entity"),
    Query("KESTREL-7 Q4 owner",                                             {"kestrel_q4"},           "rare entity + paraphrase"),
    Query("who runs the project that missed Q3",                            {"kestrel_q3", "kestrel_q4", "yuki"}, "multi-hop"),
    Query("which project does Yuki lead besides KESTREL-7 and BLAZER-3",    {"yuki"},                 "multi-hop"),
    Query("the deepest known point on Earth",                               {"mariana"},              "inference"),
    Query("why CPython doesn't have true threading",                        {"python_gil"},           "technical paraphrase"),
    Query("memory safety without garbage collection",                       {"rust_borrow"},          "technical paraphrase"),
    Query("best Italian restaurant in Brooklyn",                            set(),                    "out-of-domain", out_of_domain=True),
    Query("how to bake sourdough bread",                                    set(),                    "out-of-domain", out_of_domain=True),
    Query("asdfgh qwerty zzzz",                                             set(),                    "nonsense", out_of_domain=True),
]


@dataclass
class TextResult:
    query: Query
    hits: List[str]
    rerank_scores: List[Optional[float]]
    rank: Optional[int]
    correctly_rejected: bool


def _extract_doc_id(text: str) -> str:
    if text.startswith("[[") and "]]" in text[:32]:
        return text[2:text.index("]]")]
    return "?"


def section_text() -> Dict:
    bar("text retrieval")
    with httpx.Client(timeout=120) as c:
        vault, key = make_vault(c, "eval-text")
        H = {"X-API-Key": key}
        try:
            for d in TEXT_CORPUS:
                r = c.post(f"{BASE}/api/embed", headers=H,
                           data={"vector_store": vault, "text": d.text})
                if r.status_code != 200:
                    raise RuntimeError(f"embed {d.id}: {r.status_code} {r.text[:200]}")
            print(f"{DIM}embedded {len(TEXT_CORPUS)} docs{RESET}")
            time.sleep(0.3)

            results: List[TextResult] = []
            for q in TEXT_QUERIES:
                payload = {"store": vault, "query": q.q, "top_k": TOP_K,
                           "min_rerank_score": RERANK_FLOOR}
                r = c.post(f"{BASE}/api/retrieve",
                           headers={**H, "Content-Type": "application/json"}, json=payload)
                ctx = r.json().get("context", [])
                hits = [_extract_doc_id(x.get("text", "")) for x in ctx[:TOP_K]]
                scores = [x.get("rerank_score") for x in ctx[:TOP_K]]
                rank = next((i + 1 for i, h in enumerate(hits) if h in q.gold), None)
                results.append(TextResult(
                    query=q, hits=hits, rerank_scores=scores,
                    rank=rank,
                    correctly_rejected=q.out_of_domain and len(ctx) == 0,
                ))
        finally:
            kill_vault(c, vault)

    in_d = [r for r in results if not r.query.out_of_domain]
    ood = [r for r in results if r.query.out_of_domain]
    by_diff: Dict[str, List[TextResult]] = {}
    for r in results:
        by_diff.setdefault(r.query.difficulty, []).append(r)

    print(f"{DIM}{'difficulty':<28}{'query':<48}{'rank':<6}status{RESET}")
    print("─" * 100)
    for diff in by_diff:
        for r in by_diff[diff]:
            q = r.query
            qprint = q.q if len(q.q) <= 46 else q.q[:43] + "…"
            if q.out_of_domain:
                status = f"{G}REJECTED{RESET}" if r.correctly_rejected else f"{R}LEAKED ({len(r.hits)} hits){RESET}"
                rank = "—"
            else:
                if r.rank:
                    status = f"{G}hit @ {r.rank}{RESET}"
                else:
                    got = r.hits[:2] if r.hits else ["nothing"]
                    status = f"{R}MISS — got {got}{RESET}"
                rank = str(r.rank) if r.rank else "—"
            print(f"{diff:<28}{qprint:<48}{rank:<6}{status}")
        print()

    hit_rate = sum(1 for r in in_d if r.rank) / max(1, len(in_d))
    mrr = sum((1 / r.rank) if r.rank else 0 for r in in_d) / max(1, len(in_d))
    rej_rate = sum(1 for r in ood if r.correctly_rejected) / max(1, len(ood))

    print(f"{B}text summary{RESET}")
    print(f"  Hit@{TOP_K}:                     {hit_rate:.1%}  ({sum(1 for r in in_d if r.rank)}/{len(in_d)})")
    print(f"  MRR:                       {mrr:.3f}")
    print(f"  out-of-domain rejected:    {rej_rate:.1%}  ({sum(1 for r in ood if r.correctly_rejected)}/{len(ood)})")

    return {"section": "text", "hit_rate": hit_rate, "mrr": mrr, "ood_reject": rej_rate,
            "in_domain": len(in_d), "ood": len(ood)}


# ── image section ────────────────────────────────────────────────
#
# Synthetic images won't match real photos for visual-only retrieval,
# but BLIP captions on rendered text + the indexed filename give us a
# realistic two-signal cross-modal test.

IMAGE_FILES: List[Tuple[str, str, Tuple[int, int, int]]] = [
    # (id, dominant text rendered + filename hint, RGB tone)
    ("eiffel_img",   "EIFFEL TOWER PARIS",     (180, 200, 230)),  # hazy blue
    ("everest_img",  "MOUNT EVEREST PEAK",     (220, 220, 220)),  # snow white
    ("ocean_img",    "DEEP OCEAN TRENCH",      ( 30,  60, 110)),  # deep blue
    ("forest_img",   "GREEN FOREST CANOPY",    ( 60, 120,  60)),  # forest green
    ("desert_img",   "RED DESERT CANYON",      (180,  80,  40)),  # rust red
]


def _make_image(text: str, tone: Tuple[int, int, int]) -> bytes:
    """Render `text` on a coloured background. BLIP usually picks up the
    dominant tone; the rendered text gives the captioner literal content
    to hook on."""
    from PIL import Image, ImageDraw, ImageFont
    W, H = 512, 384
    img = Image.new("RGB", (W, H), color=tone)
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
    except Exception:
        font = ImageFont.load_default()
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((W - tw) / 2, (H - th) / 2), text, fill=(255, 255, 255), font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


IMAGE_QUERIES: List[Tuple[str, Set[str], str]] = [
    # text → image: caption + filename + visual-tone signal
    ("Paris architectural landmark",         {"eiffel_img"},   "text→image semantic"),
    ("snowy alpine summit",                  {"everest_img"},  "text→image semantic"),
    ("deep underwater chasm",                {"ocean_img"},    "text→image semantic"),
    ("dense green woodland",                 {"forest_img"},   "text→image semantic"),
    ("arid red rock canyon",                 {"desert_img"},   "text→image semantic"),
    # exact filename / caption hits via BM25
    ("Eiffel",                               {"eiffel_img"},   "text→image lexical"),
    # off-topic
    ("quantum mechanics",                    set(),            "text→image OOD",),
]


def section_image() -> Dict:
    bar("cross-modal: text → image, image → image")
    print(f"{DIM}NOTE: images here are synthetic (rendered label on coloured background). "
          f"Pure visual-semantic queries that don't match filename or BLIP caption will "
          f"miss — that's a corpus limitation, not a retrieval bug. For real photos the "
          f"system relies on PE-Core's joint text/image space which is much stronger.{RESET}")
    with httpx.Client(timeout=180) as c:
        vault, key = make_vault(c, "eval-img")
        H = {"X-API-Key": key}
        try:
            uploaded: Dict[str, bytes] = {}
            for img_id, label, tone in IMAGE_FILES:
                png = _make_image(label, tone)
                uploaded[img_id] = png
                r = c.post(f"{BASE}/api/embed", headers=H,
                           files={"file": (f"{img_id}.png", png, "image/png")},
                           data={"vector_store": vault})
                if r.status_code != 200:
                    raise RuntimeError(f"image embed {img_id}: {r.status_code} {r.text[:200]}")
            print(f"{DIM}embedded {len(IMAGE_FILES)} images{RESET}")
            time.sleep(0.5)

            print(f"{DIM}{'category':<26}{'query':<36}{'rank':<6}status{RESET}")
            print("─" * 90)
            text_in_d = []
            text_ood = []
            for q, gold, cat in IMAGE_QUERIES:
                r = c.post(f"{BASE}/api/search", headers=H,
                           data={"vector_store": vault, "query": q, "n_results": str(TOP_K),
                                 "min_rerank_score": str(RERANK_FLOOR)})
                hits_payload = r.json().get("results", [])
                hits = []
                for h in hits_payload[:TOP_K]:
                    fn = (h.get("metadata") or {}).get("filename", "")
                    hits.append(fn.replace(".png", ""))
                if not gold:
                    correct = len(hits_payload) == 0
                    text_ood.append(correct)
                    status = f"{G}REJECTED{RESET}" if correct else f"{R}LEAKED ({len(hits_payload)} hits){RESET}"
                    rank = "—"
                else:
                    rank = next((i + 1 for i, h in enumerate(hits) if h in gold), None)
                    text_in_d.append(rank)
                    status = f"{G}hit @ {rank}{RESET}" if rank else f"{R}MISS — got {hits[:2]}{RESET}"
                    rank = str(rank) if rank else "—"
                qp = q if len(q) <= 34 else q[:31] + "…"
                print(f"{cat:<26}{qp:<36}{rank:<6}{status}")

            # image → image (file query): upload one of the images again as a query
            print(f"\n{DIM}{B}image → image (file query){RESET}")
            print(f"{DIM}{'query image':<26}{'expected':<36}{'rank':<6}status{RESET}")
            print("─" * 90)
            file_in_d = []
            for img_id, png in uploaded.items():
                r = c.post(f"{BASE}/api/search", headers=H,
                           files={"file": (f"{img_id}-query.png", png, "image/png")},
                           data={"vector_store": vault, "n_results": str(TOP_K)})
                hits_payload = r.json().get("results", [])
                # The same image should rank #1 (cosine ≈ 1.0)
                hits = []
                for h in hits_payload[:TOP_K]:
                    fn = (h.get("metadata") or {}).get("filename", "")
                    hits.append(fn.replace(".png", ""))
                rank = next((i + 1 for i, h in enumerate(hits) if h == img_id), None)
                file_in_d.append(rank)
                status = f"{G}hit @ {rank}{RESET}" if rank else f"{R}MISS — got {hits[:2]}{RESET}"
                print(f"{img_id:<26}{img_id:<36}{str(rank) if rank else '—':<6}{status}")
        finally:
            kill_vault(c, vault)

    text_hits = sum(1 for r in text_in_d if r)
    text_hit_rate = text_hits / max(1, len(text_in_d))
    text_mrr = sum((1/r) if r else 0 for r in text_in_d) / max(1, len(text_in_d))
    file_hits = sum(1 for r in file_in_d if r)
    file_hit_rate = file_hits / max(1, len(file_in_d))
    ood_rate = sum(1 for r in text_ood if r) / max(1, len(text_ood))

    print(f"\n{B}image summary{RESET}")
    print(f"  text → image Hit@{TOP_K}:        {text_hit_rate:.1%}  ({text_hits}/{len(text_in_d)})")
    print(f"  text → image MRR:           {text_mrr:.3f}")
    print(f"  image → image Hit@{TOP_K}:       {file_hit_rate:.1%}  ({file_hits}/{len(file_in_d)})")
    print(f"  out-of-domain rejected:     {ood_rate:.1%}  ({sum(1 for r in text_ood if r)}/{len(text_ood)})")

    return {"section": "image",
            "text_to_image_hit": text_hit_rate, "text_to_image_mrr": text_mrr,
            "image_to_image_hit": file_hit_rate, "ood_reject": ood_rate}


# ── pdf section ──────────────────────────────────────────────────

def _make_pdf(pages: List[str]) -> bytes:
    import fitz
    doc = fitz.open()
    for txt in pages:
        page = doc.new_page(width=612, height=792)
        rect = fitz.Rect(72, 72, 540, 720)
        page.insert_textbox(rect, txt, fontsize=11, fontname="helv")
    out = doc.tobytes()
    doc.close()
    return out


PDF_PAGES = [
    # page 1
    "FRANCE - HISTORY OF MONUMENTS\n\n"
    "The Eiffel Tower in Paris was completed in 1889 for the Exposition "
    "Universelle. Designed by Gustave Eiffel, it stands 330 metres tall "
    "and remains one of the most visited paid monuments in the world. "
    "Built from puddled iron, the structure was originally intended to be "
    "dismantled after twenty years.",
    # page 2
    "MOUNTAINS - WORLD'S TALLEST PEAKS\n\n"
    "Mount Everest at 8,849 metres is the highest peak in the Himalayan "
    "range, on the border of Nepal and China. K2, the second-highest "
    "mountain at 8,611 metres, is located in the Karakoram range on the "
    "China-Pakistan border. Both peaks attract thousands of climbers each "
    "year despite the dangers.",
    # page 3
    "OCEANS - DEEPEST POINTS\n\n"
    "The Mariana Trench in the Pacific Ocean reaches a depth of 10,994 "
    "metres at the Challenger Deep, the deepest known point on Earth. The "
    "pressure at the bottom is more than 1,000 times that at sea level. "
    "Only a handful of crewed expeditions have reached the bottom.",
    # page 4
    "PROJECT KESTREL-7 STATUS REPORT\n\n"
    "Project KESTREL-7 missed its Q3 milestone by 14 days. Root cause: the "
    "upstream FOO-882 dependency stalled in QA. Owner Yuki Tanaka has "
    "moved the team's Q4 focus to the FOO-882 retry path. Estimated unblock "
    "is late November. Yuki also leads BLAZER-3 and the FOO-882 platform.",
]

PDF_QUERIES: List[Tuple[str, Set[str], str]] = [
    ("Gustave Eiffel and the 1889 Exposition",                    {"1"},      "specific page (page 1)"),
    ("border between Nepal and China",                            {"2"},      "specific page (page 2)"),
    ("pressure at the deepest known point",                       {"3"},      "specific page (page 3)"),
    ("FOO-882 retry path Q4 owner",                               {"4"},      "specific page (page 4)"),
    ("which page mentions both Mount Everest and K2",             {"2"},      "page-aware"),
    ("Yuki Tanaka's other projects",                              {"4"},      "specific page (page 4)"),
]


def section_pdf() -> Dict:
    bar("chunked PDF: page tracking, multi-chunk recall")
    with httpx.Client(timeout=180) as c:
        vault, key = make_vault(c, "eval-pdf")
        H = {"X-API-Key": key}
        try:
            pdf = _make_pdf(PDF_PAGES)
            r = c.post(f"{BASE}/api/embed", headers=H,
                       files={"file": ("eval-multipage.pdf", pdf, "application/pdf")},
                       data={"vector_store": vault})
            if r.status_code != 200:
                raise RuntimeError(f"PDF embed: {r.status_code} {r.text[:200]}")
            n_chunks = r.json().get("chunks", 0)
            print(f"{DIM}embedded 1 PDF into {n_chunks} chunk(s){RESET}")
            time.sleep(0.3)

            print(f"{DIM}{'category':<28}{'query':<46}{'rank':<6}{'page':<6}status{RESET}")
            print("─" * 110)
            ranks = []
            for q, gold_pages, cat in PDF_QUERIES:
                r = c.post(f"{BASE}/api/retrieve",
                           headers={**H, "Content-Type": "application/json"},
                           json={"store": vault, "query": q, "top_k": TOP_K,
                                 "min_rerank_score": RERANK_FLOOR})
                ctx = r.json().get("context", [])
                # Each ctx item has an optional `page` field (comma-separated string).
                first = ctx[0] if ctx else None
                top_page = (first or {}).get("page", "—") if first else "—"
                # rank = position of any chunk whose `page` set intersects gold_pages
                rank = None
                for i, item in enumerate(ctx, 1):
                    pages_str = str(item.get("page", ""))
                    page_set = {p.strip() for p in pages_str.split(",") if p.strip()}
                    if page_set & gold_pages:
                        rank = i
                        break
                ranks.append(rank)
                status = f"{G}hit @ {rank}{RESET}" if rank else f"{R}MISS — top page={top_page}{RESET}"
                qp = q if len(q) <= 44 else q[:41] + "…"
                print(f"{cat:<28}{qp:<46}{str(rank) if rank else '—':<6}{str(top_page):<6}{status}")
        finally:
            kill_vault(c, vault)

    hits = sum(1 for r in ranks if r)
    hit_rate = hits / max(1, len(ranks))
    mrr = sum((1/r) if r else 0 for r in ranks) / max(1, len(ranks))

    print(f"\n{B}PDF summary{RESET}")
    print(f"  Hit@{TOP_K} (correct page): {hit_rate:.1%}  ({hits}/{len(ranks)})")
    print(f"  MRR:                  {mrr:.3f}")
    print(f"  chunks per page:      {n_chunks / len(PDF_PAGES):.1f} (avg)")

    return {"section": "pdf", "hit_rate": hit_rate, "mrr": mrr, "chunks": n_chunks}


# ── audio section ────────────────────────────────────────────────

AUDIO_CLIPS: List[Tuple[str, str]] = [
    ("fox",     "The quick brown fox jumps over the lazy dog near the riverbank."),
    ("photo",   "Photosynthesis is the process by which green plants convert sunlight into chemical energy."),
    ("eiffel",  "The Eiffel Tower in Paris stands three hundred and thirty metres tall and was completed in eighteen eighty nine."),
]

AUDIO_QUERIES: List[Tuple[str, Set[str], str]] = [
    ("fast animal jumping over a sleeping dog",         {"fox"},     "paraphrase of speech"),
    ("how plants use sunlight",                         {"photo"},   "paraphrase of speech"),
    ("height of the Eiffel Tower",                      {"eiffel"},  "fact mentioned in speech"),
    ("recipe for chocolate cake",                       set(),       "out-of-domain"),
]


def _synth_audio(text: str) -> Optional[bytes]:
    """Generate a wav clip of `text` using macOS `say`. Returns None if unavailable."""
    if sys.platform != "darwin":
        return None
    with tempfile.TemporaryDirectory() as tmp:
        aiff = Path(tmp) / "a.aiff"
        wav = Path(tmp) / "a.wav"
        try:
            subprocess.run(["say", "-o", str(aiff), text], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000",
                            str(aiff), str(wav)], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return wav.read_bytes()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None


def section_audio() -> Dict:
    bar("ASR audio: text query → speech segment")
    sample = _synth_audio("test")
    if sample is None:
        print(f"{Y}skipping: macOS `say`/`afconvert` not available{RESET}")
        return {"section": "audio", "skipped": True}

    with httpx.Client(timeout=240) as c:
        vault, key = make_vault(c, "eval-audio")
        H = {"X-API-Key": key}
        try:
            for clip_id, text in AUDIO_CLIPS:
                wav = _synth_audio(text)
                if wav is None:
                    print(f"{R}TTS failed for {clip_id}, aborting audio section{RESET}")
                    return {"section": "audio", "skipped": True}
                r = c.post(f"{BASE}/api/embed", headers=H,
                           files={"file": (f"{clip_id}.wav", wav, "audio/wav")},
                           data={"vector_store": vault})
                if r.status_code != 200:
                    raise RuntimeError(f"audio embed {clip_id}: {r.status_code} {r.text[:200]}")
                chunks = r.json().get("chunks", 0)
                print(f"{DIM}embedded {clip_id}.wav → {chunks} chunks (acoustic + ASR){RESET}")
            time.sleep(0.5)

            print(f"\n{DIM}{'category':<26}{'query':<46}{'rank':<6}status{RESET}")
            print("─" * 100)
            in_d = []
            ood = []
            for q, gold, cat in AUDIO_QUERIES:
                r = c.post(f"{BASE}/api/search", headers=H,
                           data={"vector_store": vault, "query": q, "n_results": str(TOP_K),
                                 "min_rerank_score": str(RERANK_FLOOR)})
                hits_payload = r.json().get("results", [])
                hits = []
                for h in hits_payload[:TOP_K]:
                    fn = (h.get("metadata") or {}).get("filename", "")
                    hits.append(fn.replace(".wav", ""))
                if not gold:
                    correct = len(hits_payload) == 0
                    ood.append(correct)
                    status = f"{G}REJECTED{RESET}" if correct else f"{R}LEAKED ({len(hits_payload)} hits){RESET}"
                    rank = "—"
                else:
                    rank = next((i + 1 for i, h in enumerate(hits) if h in gold), None)
                    in_d.append(rank)
                    status = f"{G}hit @ {rank}{RESET}" if rank else f"{R}MISS — got {hits[:2]}{RESET}"
                    rank = str(rank) if rank else "—"
                qp = q if len(q) <= 44 else q[:41] + "…"
                print(f"{cat:<26}{qp:<46}{rank:<6}{status}")
        finally:
            kill_vault(c, vault)

    hits = sum(1 for r in in_d if r)
    hit_rate = hits / max(1, len(in_d))
    mrr = sum((1/r) if r else 0 for r in in_d) / max(1, len(in_d))
    rej = sum(1 for r in ood if r) / max(1, len(ood))

    print(f"\n{B}audio summary{RESET}")
    print(f"  Hit@{TOP_K} (text → audio): {hit_rate:.1%}  ({hits}/{len(in_d)})")
    print(f"  MRR:                  {mrr:.3f}")
    print(f"  out-of-domain rejected: {rej:.1%}")

    return {"section": "audio", "hit_rate": hit_rate, "mrr": mrr, "ood_reject": rej}


# ── scale section ────────────────────────────────────────────────

SCALE_TARGET = 150       # docs to embed (paced under 30/min rate limit ~5 min)
SCALE_QUERY_BATCH = 30   # queries to time
SCALE_QUERIES = TEXT_QUERIES[:8]  # reuse a representative slice
# Embed rate limit is 30/minute by default — pace just under that.
SCALE_EMBED_SLEEP = 2.1


def section_scale() -> Dict:
    bar(f"scale: {SCALE_TARGET} docs, latency p50/p95")
    print(f"{DIM}rate-limited embeds — expect ~{SCALE_TARGET * SCALE_EMBED_SLEEP / 60:.1f} min for the embed phase{RESET}")
    with httpx.Client(timeout=600) as c:
        vault, key = make_vault(c, "eval-scale")
        H = {"X-API-Key": key}
        try:
            t0 = time.time()
            i = 0
            retries = 0
            while i < SCALE_TARGET:
                base = TEXT_CORPUS[i % len(TEXT_CORPUS)]
                text = f"{base.text}  (revision {i // len(TEXT_CORPUS)})"
                r = c.post(f"{BASE}/api/embed", headers=H,
                           data={"vector_store": vault, "text": text})
                if r.status_code == 429:
                    # Backend's slowapi-rate-limit; back off and retry.
                    retries += 1
                    time.sleep(5)
                    continue
                if r.status_code != 200:
                    raise RuntimeError(f"scale embed {i}: {r.status_code} {r.text[:200]}")
                i += 1
                if i % 30 == 0:
                    print(f"{DIM}  embedded {i}/{SCALE_TARGET} "
                          f"({i / (time.time() - t0):.1f}/s, {retries} backoffs){RESET}")
                time.sleep(SCALE_EMBED_SLEEP)
            embed_secs = time.time() - t0
            print(f"{DIM}embed phase: {embed_secs:.1f}s ({SCALE_TARGET/embed_secs:.1f} docs/s){RESET}")
            time.sleep(0.5)

            # Time queries — first call may be cold (BM25 rebuild), subsequent are hot
            latencies: List[float] = []
            hits = 0
            n = 0
            for k in range(SCALE_QUERY_BATCH):
                q = SCALE_QUERIES[k % len(SCALE_QUERIES)]
                t = time.time()
                r = c.post(f"{BASE}/api/retrieve",
                           headers={**H, "Content-Type": "application/json"},
                           json={"store": vault, "query": q.q, "top_k": TOP_K,
                                 "min_rerank_score": RERANK_FLOOR})
                latencies.append(time.time() - t)
                if q.out_of_domain:
                    continue
                ctx = r.json().get("context", [])
                ids = [_extract_doc_id(x.get("text", "")) for x in ctx[:TOP_K]]
                if any(h in q.gold for h in ids):
                    hits += 1
                n += 1
        finally:
            kill_vault(c, vault)

    cold = latencies[0]
    hot = latencies[1:] if len(latencies) > 1 else latencies
    p50 = statistics.median(hot)
    p95 = sorted(hot)[int(0.95 * len(hot))] if len(hot) >= 20 else max(hot)

    print(f"\n{B}scale summary{RESET}")
    print(f"  embed throughput:   {SCALE_TARGET/embed_secs:.1f} docs/s ({embed_secs:.1f}s for {SCALE_TARGET})")
    print(f"  cold query (1st):   {cold*1000:.0f} ms (includes BM25 build)")
    print(f"  hot p50:            {p50*1000:.0f} ms")
    print(f"  hot p95:            {p95*1000:.0f} ms")
    print(f"  Hit@{TOP_K} at scale:    {hits}/{n} ({hits/max(1,n):.1%})")

    return {"section": "scale", "docs": SCALE_TARGET,
            "embed_secs": embed_secs, "cold_ms": cold * 1000,
            "p50_ms": p50 * 1000, "p95_ms": p95 * 1000,
            "hit_rate": hits / max(1, n)}


# ── realmedia section: real downloaded photos/audio/video ────────
#
# Synthetic test fixtures cap visual-semantic scores. This section pulls
# real, public-domain media from stable URLs (Wikimedia + a small set of
# CDN-hosted samples), caches to ~/.cache/embed-eval/, and runs the same
# cross-modal queries against the live system. If a URL fails the item
# is skipped (with a note) — the rest still scores.

CACHE_DIR = Path.home() / ".cache" / "embed-eval"
DOWNLOAD_UA = "EMBEd-eval-bot/1.0 (https://github.com/Himanshu8881212/OpenEmbed)"

# (id, url, mime, gold queries that should hit, ood queries that shouldn't)
REAL_IMAGES: List[Tuple[str, str, str, List[str]]] = [
    ("eiffel",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a8/Tour_Eiffel_Wikimedia_Commons.jpg/800px-Tour_Eiffel_Wikimedia_Commons.jpg",
     "image/jpeg",
     ["Eiffel Tower in Paris", "iron lattice tower", "Parisian landmark at night"]),
    ("everest",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/9/90/Everest%2C_Himalayas.jpg/960px-Everest%2C_Himalayas.jpg",
     "image/jpeg",
     ["snowy mountain peak", "Himalayan summit", "highest mountain"]),
    ("octopus",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/3/32/Octopus_vulgaris_Merculiano.jpg/960px-Octopus_vulgaris_Merculiano.jpg",
     "image/jpeg",
     ["octopus illustration", "cephalopod", "sea creature with tentacles"]),
    ("cat",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Cat03.jpg/800px-Cat03.jpg",
     "image/jpeg",
     ["domestic cat", "tabby cat", "feline pet"]),
    ("forest",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/3/34/Spruce_forest_at_Holma.jpg/960px-Spruce_forest_at_Holma.jpg",
     "image/jpeg",
     ["dense conifer forest", "spruce trees in woodland", "evergreen woods"]),
]

REAL_AUDIO: List[Tuple[str, str, str, List[str]]] = [
    ("piano",   "https://www.kozco.com/tech/piano2.wav",
     "audio/wav",
     ["piano music", "classical instrument recording"]),
    ("kalimba", "https://www.learningcontainer.com/wp-content/uploads/2020/02/Kalimba.mp3",
     "audio/mpeg",
     ["kalimba thumb piano", "soft mellow instrumental"]),
]

REAL_VIDEO: List[Tuple[str, str, str, List[str]]] = [
    ("bigbuckbunny",
     "https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/360/Big_Buck_Bunny_360_10s_1MB.mp4",
     "video/mp4",
     ["big buck bunny short film", "animated rabbit cartoon"]),
]

REAL_OOD = [
    "stock market analysis Q4 2025",
    "asdfgh qwerty zzzz",
]


def _download(url: str, dest: Path) -> Optional[bytes]:
    """Cache-aware download. Returns bytes or None on failure."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest.read_bytes()
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = httpx.get(url, headers={"User-Agent": DOWNLOAD_UA},
                      follow_redirects=True, timeout=60)
    except httpx.HTTPError as e:
        print(f"  {R}download failed{RESET} {url[:60]}…  {e}")
        return None
    if r.status_code != 200:
        print(f"  {R}download {r.status_code}{RESET} {url[:60]}…")
        return None
    dest.write_bytes(r.content)
    return r.content


def _embed_real(c: httpx.Client, vault: str, H: dict,
                items: List[Tuple[str, str, str, List[str]]],
                ext_for_mime: dict) -> List[Tuple[str, str, List[str]]]:
    """Download + embed each item. Returns list of (id, filename, queries) for items
    that successfully embedded."""
    embedded = []
    for item_id, url, mime, queries in items:
        ext = ext_for_mime.get(mime, "")
        cached = CACHE_DIR / f"{item_id}{ext}"
        data = _download(url, cached)
        if data is None:
            print(f"  {Y}skip {item_id} (download failed){RESET}")
            continue
        fname = f"{item_id}{ext}"
        r = c.post(f"{BASE}/api/embed", headers=H,
                   files={"file": (fname, data, mime)},
                   data={"vector_store": vault})
        if r.status_code != 200:
            print(f"  {R}embed failed for {item_id}: {r.status_code} {r.text[:200]}{RESET}")
            continue
        chunks = r.json().get("chunks", "?")
        size_kb = len(data) // 1024
        print(f"  {DIM}{item_id:<14} {size_kb:>6} KB → {chunks} chunks{RESET}")
        embedded.append((item_id, fname, queries))
    return embedded


def section_realmedia() -> Dict:
    bar("real-world media: downloaded photos, audio, video")
    print(f"{DIM}cache: {CACHE_DIR}{RESET}")
    ext_for_mime = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "audio/wav": ".wav",
        "audio/mpeg": ".mp3",
        "video/mp4": ".mp4",
    }

    with httpx.Client(timeout=300) as c:
        vault, key = make_vault(c, "eval-real")
        H = {"X-API-Key": key}
        try:
            print(f"\n{DIM}── images ──{RESET}")
            img_items = _embed_real(c, vault, H, REAL_IMAGES, ext_for_mime)
            print(f"\n{DIM}── audio ──{RESET}")
            aud_items = _embed_real(c, vault, H, REAL_AUDIO, ext_for_mime)
            print(f"\n{DIM}── video ──{RESET}")
            vid_items = _embed_real(c, vault, H, REAL_VIDEO, ext_for_mime)
            time.sleep(0.5)

            # Build full query list with gold ids
            queries: List[Tuple[str, str, Set[str], str]] = []
            for item_id, _fn, qs in img_items + aud_items + vid_items:
                for q in qs:
                    cat = "text→image" if (item_id, _fn, qs) in img_items else \
                          "text→audio" if (item_id, _fn, qs) in aud_items else \
                          "text→video"
                    queries.append((q, item_id, {item_id}, cat))
            for q in REAL_OOD:
                queries.append((q, "ood", set(), "out-of-domain"))

            # Run text → media queries
            print(f"\n{DIM}{'category':<14}{'query':<46}{'rank':<6}status{RESET}")
            print("─" * 100)

            def _fileid(filename: str) -> str:
                # filenames are stored as "<id><ext>"; strip extension
                stem = filename
                for ext in ext_for_mime.values():
                    if stem.endswith(ext):
                        return stem[:-len(ext)]
                return stem

            in_d_ranks: List[Optional[int]] = []
            ood_ok = []
            for q, gold_id, gold_set, cat in queries:
                r = c.post(f"{BASE}/api/search", headers=H,
                           data={"vector_store": vault, "query": q,
                                 "n_results": str(TOP_K),
                                 "min_rerank_score": str(RERANK_FLOOR)})
                hits_payload = r.json().get("results", [])
                hits = []
                for h in hits_payload[:TOP_K]:
                    fn = (h.get("metadata") or {}).get("filename", "")
                    hits.append(_fileid(fn))
                if not gold_set:
                    correct = len(hits_payload) == 0
                    ood_ok.append(correct)
                    status = f"{G}REJECTED{RESET}" if correct else f"{R}LEAKED → {hits[:2]}{RESET}"
                    rank = "—"
                else:
                    rank = next((i + 1 for i, h in enumerate(hits) if h in gold_set), None)
                    in_d_ranks.append(rank)
                    status = f"{G}hit @ {rank}{RESET}" if rank else f"{R}MISS — got {hits[:2] or 'nothing'}{RESET}"
                    rank = str(rank) if rank else "—"
                qp = q if len(q) <= 44 else q[:41] + "…"
                print(f"{cat:<14}{qp:<46}{rank:<6}{status}")

            # Media → media (file query): re-upload each downloaded file as a search query
            print(f"\n{DIM}{B}media → media (file query) — same file should rank #1{RESET}")
            print(f"{DIM}{'modality':<14}{'query file':<22}{'rank':<6}status{RESET}")
            print("─" * 70)
            file_ranks: List[Optional[int]] = []
            for items, modality in [(img_items, "image"), (aud_items, "audio"), (vid_items, "video")]:
                for item_id, fname, _qs in items:
                    cached = CACHE_DIR / fname
                    data = cached.read_bytes()
                    mime = next((m for m in ext_for_mime
                                 if ext_for_mime[m] == cached.suffix), "application/octet-stream")
                    r = c.post(f"{BASE}/api/search", headers=H,
                               files={"file": (f"q-{fname}", data, mime)},
                               data={"vector_store": vault, "n_results": str(TOP_K)})
                    hits_payload = r.json().get("results", [])
                    hits = [_fileid((h.get("metadata") or {}).get("filename", ""))
                            for h in hits_payload[:TOP_K]]
                    rank = next((i + 1 for i, h in enumerate(hits) if h == item_id), None)
                    file_ranks.append(rank)
                    status = f"{G}hit @ {rank}{RESET}" if rank else f"{R}MISS{RESET}"
                    print(f"{modality:<14}{item_id:<22}{str(rank) if rank else '—':<6}{status}")
        finally:
            kill_vault(c, vault)

    in_d_total = len(in_d_ranks)
    in_d_hits = sum(1 for r in in_d_ranks if r)
    hit_rate = in_d_hits / max(1, in_d_total)
    mrr = sum((1 / r) if r else 0 for r in in_d_ranks) / max(1, in_d_total)
    file_total = len(file_ranks)
    file_hits = sum(1 for r in file_ranks if r)
    file_rate = file_hits / max(1, file_total)
    rej = sum(1 for r in ood_ok if r) / max(1, len(ood_ok))

    print(f"\n{B}realmedia summary{RESET}")
    print(f"  text → media Hit@{TOP_K}:  {hit_rate:.1%}  ({in_d_hits}/{in_d_total})")
    print(f"  text → media MRR:      {mrr:.3f}")
    print(f"  media → media Hit@{TOP_K}: {file_rate:.1%}  ({file_hits}/{file_total})")
    print(f"  out-of-domain rejected: {rej:.1%}")

    return {"section": "realmedia",
            "text_hit": hit_rate, "text_mrr": mrr,
            "file_hit": file_rate, "ood_reject": rej,
            "in_domain": in_d_total, "ood": len(ood_ok)}


# ── orchestration ────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--section", default="all",
                        help="comma-separated subset of: text,image,pdf,audio,scale (default: all)")
    args = parser.parse_args()

    requested = [s.strip() for s in args.section.split(",")] if args.section != "all" else \
                ["text", "realmedia", "pdf", "audio", "scale"]

    print(f"{B}EMBEd retrieval evaluation{RESET}")
    print(f"{DIM}base: {BASE}  top_k={TOP_K}  rerank_floor={RERANK_FLOOR}{RESET}")
    print(f"{DIM}sections: {', '.join(requested)}{RESET}")

    # preflight
    try:
        r = httpx.get(f"{BASE}/api/health", timeout=5)
        if r.status_code != 200 or not r.json().get("perception_encoder"):
            print(f"{R}backend not ready at {BASE}{RESET}")
            return 1
    except httpx.HTTPError as e:
        print(f"{R}cannot reach {BASE}: {e}{RESET}")
        return 1

    summaries: List[Dict] = []
    runners = {
        "text": section_text,
        "image": section_image,            # synthetic; kept for diagnosis
        "realmedia": section_realmedia,    # downloaded real photos / audio / video
        "pdf": section_pdf,
        "audio": section_audio,
        "scale": section_scale,
    }
    for s in requested:
        if s not in runners:
            print(f"{Y}unknown section {s!r} — skipping{RESET}")
            continue
        try:
            summaries.append(runners[s]())
        except Exception as e:
            print(f"{R}{s} section crashed: {e}{RESET}")
            summaries.append({"section": s, "error": str(e)})

    # final aggregate
    print(f"\n{B}═══ overall ═══{RESET}")
    for s in summaries:
        sec = s.get("section", "?")
        if s.get("skipped"):
            print(f"  {sec:<8} skipped")
            continue
        if "error" in s:
            print(f"  {sec:<8} {R}error: {s['error']}{RESET}")
            continue
        line = f"  {sec:<8}"
        if "hit_rate" in s:
            line += f" Hit@{TOP_K}={s['hit_rate']:.0%}"
        if "mrr" in s:
            line += f" MRR={s['mrr']:.2f}"
        if "text_to_image_hit" in s:
            line += f" txt→img={s['text_to_image_hit']:.0%} img→img={s['image_to_image_hit']:.0%}"
        if "ood_reject" in s:
            line += f" OOD={s['ood_reject']:.0%}"
        if "p95_ms" in s:
            line += f" p50={s['p50_ms']:.0f}ms p95={s['p95_ms']:.0f}ms ({s['docs']} docs)"
        print(line)

    return 0


if __name__ == "__main__":
    sys.exit(main())
