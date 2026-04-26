"""Speech-to-text for indexing speech audio as searchable text chunks.

PE-AV audio embeddings encode acoustic properties — they're great for
"find the part with thunder" but blind to *what is being said*. Adding ASR
turns spoken content into text chunks that the existing text retrieval stack
(PE-Core text space + BM25 + reranker) can match perfectly.

Design
------
- Lazy-loaded; first call downloads whisper-base (~140 MB) and pins it on the
  best available device (CUDA > MPS > CPU).
- `transcribe_audio` returns time-aligned segments. Caller decides whether to
  treat them as text chunks for indexing.
- Failures degrade gracefully: empty list, no exception. Audio still gets the
  acoustic PE-AV chunks so non-speech queries keep working.
- Hallucination filter: Whisper happily produces walls of "❤️ ❤️ ❤️" or
  "Thank you. Thank you. Thank you." on non-speech audio (e.g. thunder, music).
  These pollute BM25 and the text retrieval space. We drop segments that fail
  a "looks like speech" sanity check before returning.
"""
from __future__ import annotations
from collections import Counter
from typing import Any, Dict, List
import os
import tempfile
import threading

from app.core.logger import app_logger as logger

_MODEL_NAME = os.environ.get("ASR_MODEL", "openai/whisper-base")
# ASR_STRICT=1 keeps the old aggressive hallucination filter (English-leaning).
# Default is relaxed so short transcripts and non-Latin scripts pass through.
_STRICT = os.environ.get("ASR_STRICT", "").lower() in ("1", "true", "yes")

_pipeline = None
_load_lock = threading.Lock()
_available = True  # flips False if loading raises


def _device() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


def _get_pipeline():
    global _pipeline, _available
    if _pipeline is not None:
        return _pipeline
    if not _available:
        return None
    with _load_lock:
        if _pipeline is not None:
            return _pipeline
        if not _available:
            return None
        try:
            from transformers import pipeline
            dev = _device()
            logger.info(f"Loading Whisper ASR ({_MODEL_NAME}) on device={dev}…")
            _pipeline = pipeline(
                "automatic-speech-recognition",
                model=_MODEL_NAME,
                device=dev,
                chunk_length_s=30,
                stride_length_s=(5, 5),
                return_timestamps=True,
            )
            logger.info("Whisper ASR ready")
        except Exception as e:
            logger.warning(f"Whisper ASR unavailable: {e}")
            _available = False
            return None
    return _pipeline


def is_available() -> bool:
    return _available


def _looks_like_speech(text: str) -> bool:
    """Heuristic: does this transcript look like real speech, or Whisper babble?

    Targets Whisper's three common hallucination patterns on non-speech audio:
      1. Emoji / symbol walls   -> low letter ratio
      2. "Thank you." × N       -> one word dominates
      3. "♪♪♪♪♪♪"              -> low character diversity

    Thresholds are deliberately permissive (short utterances, CJK / non-Latin
    scripts pass): ASR_STRICT=1 reverts to the tighter English-leaning rules.
    """
    text = (text or "").strip()

    min_len = 8 if _STRICT else 4
    letter_ratio_min = 0.5 if _STRICT else 0.4
    char_diversity_min = 6 if _STRICT else 4

    if len(text) < min_len:
        if text:
            logger.debug(f"ASR drop (too short): {text!r}")
        return False

    # 1. Letter ratio — real speech is mostly letters + spaces + light punctuation.
    #    str.isalpha() is unicode-aware (CJK, Cyrillic, Arabic all count as letters).
    letters = sum(1 for c in text if c.isalpha())
    if letters / len(text) < letter_ratio_min:
        logger.debug(f"ASR drop (low letter ratio): {text!r}")
        return False

    # 2. Word-repetition collapse — only meaningful with enough words to detect a loop.
    words = [w.lower().strip(".,!?;:'\"") for w in text.split()]
    words = [w for w in words if w]
    if len(words) >= 6:
        most, count = Counter(words).most_common(1)[0]
        if count / len(words) > 0.6:
            logger.debug(f"ASR drop (word loop {most!r}): {text!r}")
            return False
        unique_ratio = len(set(words)) / len(words)
        if unique_ratio < 0.35:
            logger.debug(f"ASR drop (low unique-word ratio): {text!r}")
            return False

    # 3. Character diversity — fewer than N unique chars means nothing useful.
    if len(set(text.lower())) < char_diversity_min:
        logger.debug(f"ASR drop (low char diversity): {text!r}")
        return False

    return True


def transcribe_audio(audio_bytes: bytes, ext: str = ".wav") -> List[Dict[str, Any]]:
    """Transcribe speech audio into time-aligned segments.

    Returns
    -------
    list of {"text": str, "start_sec": float | None, "end_sec": float | None}
    Empty list when ASR is unavailable, the file isn't speech, or transcription
    fails. Callers should fall back to acoustic embeddings in that case.
    """
    p = _get_pipeline()
    if p is None:
        return []

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
        f.write(audio_bytes)
        path = f.name
    try:
        result = p(path)
    except Exception as e:
        logger.warning(f"Whisper transcription failed: {e}")
        return []
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass

    out: List[Dict[str, Any]] = []
    for c in (result.get("chunks") or []):
        text = (c.get("text") or "").strip()
        if not _looks_like_speech(text):
            continue
        ts = c.get("timestamp")
        if isinstance(ts, (list, tuple)) and len(ts) == 2:
            s, e = ts
        else:
            s, e = None, None
        out.append({
            "text": text,
            "start_sec": float(s) if s is not None else None,
            "end_sec": float(e) if e is not None else None,
        })

    if not out:
        full_text = (result.get("text") or "").strip()
        if _looks_like_speech(full_text):
            out.append({"text": full_text, "start_sec": None, "end_sec": None})

    if not out:
        logger.info("ASR: no speech-like content detected — falling back to acoustic chunks only")

    return out
