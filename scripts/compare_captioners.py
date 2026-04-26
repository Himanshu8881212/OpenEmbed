#!/usr/bin/env python3
"""A/B compare BLIP vs MiniCPM captions on the cached eval images + the
BBB video keyframes. Run AFTER downloading the GGUFs and ensuring
`llama-server` is on PATH.

Usage:
    python scripts/compare_captioners.py
"""
from __future__ import annotations
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image  # noqa: E402

CACHE = Path.home() / ".cache" / "embed-eval"
G = "\033[32m"; Y = "\033[33m"; B = "\033[1m"; DIM = "\033[2m"; RESET = "\033[0m"


def png_bytes(path: Path) -> bytes:
    """Normalise to PNG bytes — captioners accept PNG; some inputs are JPG."""
    img = Image.open(path).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def collect_inputs() -> list:
    items: list = []
    # Real downloaded photos
    for name in ("eiffel.jpg", "everest.jpg", "octopus.jpg", "cat.jpg", "forest.jpg"):
        p = CACHE / name
        if p.exists():
            items.append((name, png_bytes(p)))
    # BBB video keyframes — extract one per second × first 4 seconds
    bbb = CACHE / "bigbuckbunny.mp4"
    if bbb.exists():
        try:
            import av
            container = av.open(str(bbb))
            stream = container.streams.video[0]
            time_base = float(stream.time_base) if stream.time_base else 1 / 30
            frames = []
            for fr in container.decode(video=0):
                ts = float(fr.pts) * time_base if fr.pts is not None else 0
                if any(abs(ts - t) < 0.05 for t in (1.0, 3.0, 5.0, 7.0)):
                    img = Image.fromarray(fr.to_ndarray(format="rgb24"))
                    buf = io.BytesIO(); img.save(buf, format="PNG")
                    frames.append((f"bbb-t{ts:.0f}s", buf.getvalue()))
                    if len(frames) >= 4:
                        break
            container.close()
            items.extend(frames)
        except Exception as e:
            print(f"{Y}skipping BBB frames: {e}{RESET}")
    return items


def main() -> int:
    items = collect_inputs()
    if not items:
        print("No cached eval inputs found. Run scripts/eval.py first.")
        return 1

    print(f"{B}A/B captioner comparison{RESET}")
    print(f"{DIM}{len(items)} inputs from {CACHE}{RESET}\n")

    # BLIP
    os.environ["CAPTIONER"] = "blip"
    from app.services import image_captioner as blip_mod
    blip_mod._BACKEND = "blip"  # honour the override after import-time read
    blip_caps = []
    print(f"{B}BLIP{RESET}")
    for name, data in items:
        cap = blip_mod.caption_image(data)
        print(f"  {name:<18}  {cap!r}")
        blip_caps.append(cap)

    # MiniCPM
    print(f"\n{B}MiniCPM-o-4.5 (Q4_0){RESET}")
    os.environ["CAPTIONER"] = "minicpm"
    blip_mod._BACKEND = "minicpm"
    minicpm_caps = []
    for name, data in items:
        cap = blip_mod.caption_image(data)
        print(f"  {name:<18}  {cap!r}")
        minicpm_caps.append(cap)

    # Side-by-side
    print(f"\n{B}side-by-side{RESET}")
    print(f"{DIM}{'input':<18}{'BLIP':<55}MiniCPM-o-4.5{RESET}")
    print("─" * 130)
    for (name, _), b, m in zip(items, blip_caps, minicpm_caps):
        b_short = (b or "—")[:50]
        m_short = (m or "—")[:60]
        print(f"{name:<18}{b_short:<55}{m_short}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
