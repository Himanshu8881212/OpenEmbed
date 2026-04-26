"""Image captioning for indexing — gives image chunks real prose document text.

Why: the cross-encoder reranker scores chunks against the query using their
text. Without a caption, an image chunk's text is the synthesized
``"image eiffel_tower"`` form — better than nothing but still loses to
unrelated speech transcripts on cross-encoder length bias. A real caption
("a black-and-white photo of the eiffel tower at night") gives the reranker
proper sentence-shaped, content-aligned text to score.

Backend selection
-----------------
Default backend is BLIP-base (~440 MB) — small, fast, photorealistic-only.
Set ``CAPTIONER=minicpm`` to use MiniCPM-o-4.5 via llama-server (richer,
style-aware captions; closes BLIP's "animated/cartoon" blind spot). If the
MiniCPM backend isn't available at request time we transparently fall
back to BLIP so the pipeline never breaks.
"""
from __future__ import annotations
import io
import os
import threading
from typing import Optional

from PIL import Image

from app.core.logger import app_logger as logger

_MODEL_NAME = os.environ.get("CAPTION_MODEL", "Salesforce/blip-image-captioning-base")
_BACKEND = os.environ.get("CAPTIONER", "blip").lower()  # blip | minicpm
_model = None
_processor = None
_device_str = None
_load_lock = threading.Lock()
_available = True


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


def _get_model():
    """Load (model, processor, device) on first call. Returns None on failure."""
    global _model, _processor, _device_str, _available
    if _model is not None:
        return _model, _processor, _device_str
    if not _available:
        return None
    with _load_lock:
        if _model is not None:
            return _model, _processor, _device_str
        if not _available:
            return None
        try:
            import torch
            from transformers import AutoProcessor, BlipForConditionalGeneration
            dev = _device()
            logger.info(f"Loading image captioner ({_MODEL_NAME}) on device={dev}…")
            _processor = AutoProcessor.from_pretrained(_MODEL_NAME)
            mdl = BlipForConditionalGeneration.from_pretrained(_MODEL_NAME)
            mdl = mdl.to(dev).eval()
            _model = mdl
            _device_str = dev
            logger.info("Image captioner ready")
        except Exception as e:
            logger.warning(f"Image captioner unavailable: {e}")
            _available = False
            return None
    return _model, _processor, _device_str


def is_available() -> bool:
    return _available


def caption_image(image_bytes: bytes) -> Optional[str]:
    """Generate a one-sentence caption for the image. Returns None on failure.

    When CAPTIONER=minicpm we try MiniCPM-o-4.5 first; on any failure
    (server not running, file missing, request timeout) we silently fall
    back to BLIP so indexing never breaks.
    """
    if _BACKEND == "minicpm":
        try:
            from app.services import minicpm_captioner
            text = minicpm_captioner.caption_image(image_bytes)
            if text:
                return text
        except Exception as e:
            logger.warning(f"MiniCPM captioner errored, falling back to BLIP: {e}")
        # else: fall through to BLIP below

    return _caption_with_blip(image_bytes)


def _caption_with_blip(image_bytes: bytes) -> Optional[str]:
    got = _get_model()
    if got is None:
        return None
    model, processor, dev = got
    try:
        import torch
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        inputs = processor(images=img, return_tensors="pt").to(dev)
        with torch.inference_mode():
            out_ids = model.generate(**inputs, max_new_tokens=40, num_beams=3)
        text = processor.decode(out_ids[0], skip_special_tokens=True).strip()
        return text or None
    except Exception as e:
        logger.warning(f"Image captioning failed: {e}")
        return None
