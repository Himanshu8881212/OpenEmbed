"""
Meta Perception Encoder service — joint multimodal embeddings.

Two encoders, three aligned spaces (PE-core does NOT share space with PE-AV):
- PE-Core (image + text)        → 1024-dim CLIP-style shared space
- PE-AV   (audio + video + text) → separate text encoders per modality pair

Each vault stores three sub-collections; text chunks index into all three.

MPS optimizations applied:
- fp16 on PE-Core and PE-AV (configurable via PE_DTYPE env, default float16)
- Eager warmup on initialize() to pay compile/cache costs upfront
- torch.inference_mode() everywhere on hot paths (faster than no_grad)
- L2-normalize on GPU before .cpu() to avoid extra round-trip
- Explicit free of CPU model copies + torch.mps.empty_cache() after .to(device)
- Optional lazy PE-AV loading via PE_AV_LAZY=1 (default eager)
"""
from typing import List, Dict, Optional, Any
import io
import os
import tempfile
import gc

import torch
import numpy as np
from PIL import Image

from app.core.config import settings
from app.core.logger import app_logger as logger


_device: Optional[torch.device] = None
_dtype: Optional[torch.dtype] = None
_core_model = None
_core_preprocess = None
_core_tokenizer = None
_av_model = None
_av_processor = None

EMBEDDING_DIM = 1024
SPACES = ("image", "audio", "video")


def _resolve_dtype() -> torch.dtype:
    """Pick the inference dtype. Default is float16 on MPS/CUDA, float32 on CPU."""
    global _dtype
    if _dtype is not None:
        return _dtype
    raw = (os.getenv("PE_DTYPE") or settings.pe_dtype or "").strip().lower()
    device = _get_device()
    if raw in ("fp16", "float16", "half"):
        _dtype = torch.float16
    elif raw in ("bf16", "bfloat16"):
        _dtype = torch.bfloat16
    elif raw in ("fp32", "float32", "float", ""):
        # Default behaviour: fp16 on accelerator, fp32 on cpu
        _dtype = torch.float16 if device.type in ("mps", "cuda") else torch.float32
    else:
        logger.warning(f"Unknown PE_DTYPE={raw!r}, falling back to float32")
        _dtype = torch.float32
    return _dtype


def _get_device() -> torch.device:
    global _device
    if _device is None:
        if torch.backends.mps.is_available():
            _device = torch.device("mps")
        elif torch.cuda.is_available():
            _device = torch.device("cuda")
        else:
            _device = torch.device("cpu")
        logger.info(f"PE device: {_device}")
    return _device


def _free_cpu_copies():
    """Release any lingering CPU weight references after .to(device)."""
    gc.collect()
    if _get_device().type == "mps":
        try:
            torch.mps.empty_cache()
        except Exception:
            pass
    elif _get_device().type == "cuda":
        try:
            torch.cuda.empty_cache()
        except Exception:
            pass


def _load_core():
    global _core_model, _core_preprocess, _core_tokenizer
    if _core_model is None:
        import core.vision_encoder.pe as pe
        import core.vision_encoder.transforms as transforms

        device = _get_device()
        dtype = _resolve_dtype()
        config_name = os.getenv("PE_CORE_MODEL", "PE-Core-L14-336")
        logger.info(f"Loading {config_name} (dtype={dtype})...")
        model = pe.CLIP.from_config(config_name, pretrained=True)
        model = model.to(device=device, dtype=dtype).eval()
        _core_model = model
        _core_preprocess = transforms.get_image_transform(_core_model.image_size)
        _core_tokenizer = transforms.get_text_tokenizer(_core_model.context_length)
        _free_cpu_copies()
        logger.info(
            f"PE-Core ready (image_size={_core_model.image_size}, "
            f"context_length={_core_model.context_length}, dtype={dtype})"
        )
    return _core_model, _core_preprocess, _core_tokenizer


def _load_av():
    global _av_model, _av_processor
    if _av_model is None:
        from transformers import PeAudioVideoModel, PeAudioVideoProcessor

        device = _get_device()
        dtype = _resolve_dtype()
        ckpt = os.getenv("PE_AV_MODEL", "facebook/pe-av-large")
        logger.info(f"Loading {ckpt} (dtype={dtype})...")
        # Load directly in target dtype to avoid building a full fp32 copy first.
        try:
            model = PeAudioVideoModel.from_pretrained(ckpt, torch_dtype=dtype)
        except TypeError:
            # Older transformers signature
            model = PeAudioVideoModel.from_pretrained(ckpt).to(dtype)
        model = model.to(device).eval()
        _av_model = model
        _av_processor = PeAudioVideoProcessor.from_pretrained(ckpt, sampling_rate=16000)
        _free_cpu_copies()
        logger.info(f"PE-AV ready (dtype={dtype})")
    return _av_model, _av_processor


def _av_text_features(text: str):
    """Run text through PE-AV's ModernBERT and return CLS embedding (1, 1024)."""
    return _av_text_features_batch([text])


def _av_text_features_batch(texts: List[str]):
    """Batched version of _av_text_features. Returns CLS embeddings (N, 1024).

    Output dtype matches the model dtype; callers downcast/normalize as needed.
    """
    model, processor = _load_av()
    inputs = processor(text=list(texts), return_tensors="pt", padding=True)
    # Token ids stay int64; only the float embedding outputs adopt model dtype.
    inputs = {k: (v.to(_get_device()) if hasattr(v, "to") else v) for k, v in inputs.items()}
    with torch.inference_mode():
        out = model.text_model(
            input_ids=inputs["input_ids"],
            attention_mask=inputs.get("attention_mask"),
            output_hidden_states=True,
        )
    return out.hidden_states[-1][:, 0]  # CLS token, shape (N, 1024)


# ── Memory + warmup helpers ────────────────────────────────────────

def memory_stats() -> Dict[str, object]:
    """Return current device + MPS memory usage. Safe to call before/after init."""
    device = _get_device()
    stats: Dict[str, object] = {
        "device": str(device),
        "dtype": str(_resolve_dtype()).replace("torch.", ""),
    }
    if device.type == "mps":
        try:
            stats["mps_allocated_mb"] = round(torch.mps.current_allocated_memory() / 1e6, 1)
            stats["mps_reserved_mb"] = round(torch.mps.driver_allocated_memory() / 1e6, 1)
        except Exception as e:
            stats["mps_error"] = str(e)
    elif device.type == "cuda":
        try:
            stats["cuda_allocated_mb"] = round(torch.cuda.memory_allocated() / 1e6, 1)
            stats["cuda_reserved_mb"] = round(torch.cuda.memory_reserved() / 1e6, 1)
        except Exception as e:
            stats["cuda_error"] = str(e)
    return stats


def _warmup():
    """One synthetic forward pass per modality so the first real request is hot."""
    try:
        # Text + image via PE-Core
        encode_text_for_image("warmup text")
        tiny = Image.new("RGB", (64, 64), color=(128, 128, 128))
        buf = io.BytesIO()
        tiny.save(buf, format="PNG")
        encode_image(buf.getvalue())

        # PE-AV: text-for-audio also exercises the audio projection head;
        # text-for-video exercises the video projection head.
        encode_text_for_audio("warmup text")
        encode_text_for_video("warmup text")

        # Real audio + video forwards (1s of silence + 8 black frames)
        try:
            import wave, struct
            sr = 16000
            wav_buf = io.BytesIO()
            with wave.open(wav_buf, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sr)
                w.writeframes(struct.pack("<" + "h" * sr, *([0] * sr)))
            encode_audio(wav_buf.getvalue(), ext=".wav")
        except Exception as e:
            logger.warning(f"audio warmup skipped: {e}")

        try:
            import av
            vid_buf = io.BytesIO()
            container = av.open(vid_buf, mode="w", format="mp4")
            stream = container.add_stream("h264", rate=8)
            stream.width, stream.height = 64, 64
            stream.pix_fmt = "yuv420p"
            for _ in range(8):
                arr = np.zeros((64, 64, 3), dtype=np.uint8)
                frame = av.VideoFrame.from_ndarray(arr, format="rgb24")
                for packet in stream.encode(frame):
                    container.mux(packet)
            for packet in stream.encode():
                container.mux(packet)
            container.close()
            encode_video(vid_buf.getvalue(), ext=".mp4")
        except Exception as e:
            logger.warning(f"video warmup skipped: {e}")
    finally:
        _free_cpu_copies()


def _maybe_compile():
    """Wrap loaded models with torch.compile if PE_COMPILE is set."""
    global _core_model, _av_model
    enabled = (os.getenv("PE_COMPILE", "").lower() in ("1", "true", "yes")
               or getattr(settings, "pe_compile", False))
    if not enabled:
        return
    try:
        if _core_model is not None and not hasattr(_core_model, "_orig_mod"):
            logger.info("torch.compile PE-Core (mode=reduce-overhead)...")
            _core_model = torch.compile(_core_model, mode="reduce-overhead")
        if _av_model is not None and not hasattr(_av_model, "_orig_mod"):
            logger.info("torch.compile PE-AV (mode=reduce-overhead)...")
            _av_model = torch.compile(_av_model, mode="reduce-overhead")
    except Exception as e:
        logger.warning(f"torch.compile failed, continuing un-compiled: {e}")


def initialize() -> bool:
    """Eagerly load both models so first request isn't a 4-minute wait.

    Set PE_AV_LAZY=1 (or settings.pe_av_lazy=true) to defer PE-AV until first
    audio/video request — saves ~8GB at startup but makes the first such
    request slow.
    """
    try:
        _load_core()
        lazy_av = (os.getenv("PE_AV_LAZY", "").lower() in ("1", "true", "yes")
                   or getattr(settings, "pe_av_lazy", False))
        if lazy_av:
            logger.info("PE-AV deferred (PE_AV_LAZY enabled) — first audio/video request will load it")
        else:
            _load_av()
        _maybe_compile()
        # Warmup — even if lazy, we warm what's loaded (PE-Core only).
        try:
            if not lazy_av:
                _warmup()
            else:
                # PE-Core warmup only
                encode_text_for_image("warmup text")
                tiny = Image.new("RGB", (64, 64), color=(128, 128, 128))
                buf = io.BytesIO()
                tiny.save(buf, format="PNG")
                encode_image(buf.getvalue())
                _free_cpu_copies()
        except Exception as e:
            logger.warning(f"warmup partial failure: {e}")
        logger.info(f"perception memory: {memory_stats()}")
        return True
    except Exception as e:
        logger.error(f"Perception Encoder init failed: {e}")
        return False


def is_ready() -> bool:
    """PE-Core must be loaded; PE-AV may be deferred under PE_AV_LAZY."""
    return _core_model is not None


# ── Encoders ────────────────────────────────────────────────────

def _normalize(t: torch.Tensor) -> torch.Tensor:
    return t / (t.norm(dim=-1, keepdim=True) + 1e-8)


def _to_float_list(t: torch.Tensor) -> List[float]:
    """Cast device tensor → fp32 cpu list (the public API contract)."""
    return t.detach().to(dtype=torch.float32, device="cpu").tolist()


def encode_image(image_bytes: bytes) -> List[float]:
    """Image → PE-Core space (single global embedding)."""
    model, preprocess, _ = _load_core()
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    tensor = preprocess(img).unsqueeze(0).to(_get_device(), dtype=_resolve_dtype())
    with torch.inference_mode():
        feat = model.encode_image(tensor)
        feat = _normalize(feat)
    return _to_float_list(feat[0])


def encode_image_tiles(image_bytes: bytes, *, tile_grid: int = 2,
                       include_full: bool = True) -> List[Dict[str, Any]]:
    """Tile-based image embedding for region-level retrieval.

    A single global embedding smears: a query about "the dog" doesn't
    strongly match a wide photo where the dog is just one element. We crop
    the image into a NxN grid (default 2x2 = 4 quadrants) and embed each
    region in addition to the full image. Total: 1 + tile_grid² embeddings
    per image (5 by default).

    Returns list of dicts: {"region": str, "bbox": [x0,y0,x1,y1],
                            "embedding": List[float]}
    """
    model, preprocess, _ = _load_core()
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    W, H = img.size

    crops: List[Dict[str, Any]] = []
    if include_full:
        crops.append({"region": "full", "bbox": [0, 0, W, H], "image": img})

    if tile_grid >= 2:
        # Use 50% overlap between tiles by drawing them at halfsize+halfstep so
        # objects on quadrant borders aren't sliced. For 2x2 this gives 4 tiles.
        tw, th = W // tile_grid, H // tile_grid
        for r in range(tile_grid):
            for c in range(tile_grid):
                x0 = c * tw
                y0 = r * th
                x1 = W if c == tile_grid - 1 else (c + 1) * tw
                y1 = H if r == tile_grid - 1 else (r + 1) * th
                region_name = _grid_region_name(r, c, tile_grid)
                crops.append({
                    "region": region_name,
                    "bbox": [x0, y0, x1, y1],
                    "image": img.crop((x0, y0, x1, y1)),
                })

    # Batch through PE-Core
    batch = torch.stack([preprocess(c["image"]) for c in crops]).to(
        _get_device(), dtype=_resolve_dtype()
    )
    with torch.inference_mode():
        feats = model.encode_image(batch)
        feats = _normalize(feats)

    out = []
    for crop, feat in zip(crops, feats):
        out.append({
            "region": crop["region"],
            "bbox": crop["bbox"],
            "embedding": _to_float_list(feat),
        })
    return out


def _grid_region_name(r: int, c: int, grid: int) -> str:
    if grid == 2:
        return ["top-left", "top-right", "bottom-left", "bottom-right"][r * grid + c]
    return f"r{r}c{c}"


def encode_text_for_image(text: str) -> List[float]:
    """Text → PE-Core space (alignable with images)."""
    model, _, tok = _load_core()
    tokens = tok([text]).to(_get_device())
    with torch.inference_mode():
        feat = model.encode_text(tokens)
        feat = _normalize(feat)
    return _to_float_list(feat[0])


def encode_audio(audio_bytes: bytes, ext: str = ".wav") -> List[float]:
    """Audio → PE-AV audio space (single global embedding for the whole clip).

    Kept for backward compatibility and for the search-by-audio query path. For
    indexing long clips, prefer ``encode_audio_windows`` so each retrievable
    chunk is bounded in time.
    """
    import librosa

    model, processor = _load_av()
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
        f.write(audio_bytes)
        path = f.name
    try:
        wav, _sr = librosa.load(path, sr=16000, mono=True)
    finally:
        os.unlink(path)
    return _encode_audio_segment(wav, model, processor)


def _encode_audio_segment(wav, model, processor) -> List[float]:
    """Embed one already-loaded mono 16kHz audio segment."""
    inputs = processor(audio=[wav], return_tensors="pt")
    dtype = _resolve_dtype()
    inputs = {
        k: (v.to(_get_device(), dtype=dtype) if hasattr(v, "to") and v.dtype.is_floating_point
            else (v.to(_get_device()) if hasattr(v, "to") else v))
        for k, v in inputs.items()
    }
    with torch.inference_mode():
        feat = model.get_audio_embeds(input_values=inputs["input_values"])
        feat = _normalize(feat[0])
    return _to_float_list(feat)


def encode_audio_windows(
    audio_bytes: bytes,
    ext: str = ".wav",
    window_sec: float = 30.0,
    overlap_sec: float = 5.0,
    min_window_sec: float = 1.0,
) -> List[Dict[str, Any]]:
    """Sliding-window audio embeddings for long clips.

    Each window is 30s by default with 5s overlap (stride 25s). Short clips
    (<= window_sec) yield a single window covering the whole audio.

    Returns: list of {"start_sec": float, "end_sec": float, "embedding": [..]}
    """
    import librosa

    model, processor = _load_av()
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
        f.write(audio_bytes)
        path = f.name
    try:
        wav, sr = librosa.load(path, sr=16000, mono=True)
    finally:
        os.unlink(path)

    if sr != 16000:
        # librosa's sr= forces resample, so this is just a sanity check
        raise RuntimeError(f"unexpected sample rate {sr}")

    n_samples = len(wav)
    duration_sec = n_samples / sr
    win_len = int(window_sec * sr)
    stride = int((window_sec - overlap_sec) * sr)
    if stride <= 0:
        raise ValueError(f"overlap_sec ({overlap_sec}) must be < window_sec ({window_sec})")

    if duration_sec <= window_sec:
        slices = [(0, n_samples)]
    else:
        slices = []
        start = 0
        while start < n_samples:
            end = min(start + win_len, n_samples)
            slices.append((start, end))
            if end == n_samples:
                break
            start += stride
        # Drop a tail window shorter than min_window_sec if it fully overlaps the prior one
        if len(slices) >= 2:
            s_last, e_last = slices[-1]
            if (e_last - s_last) / sr < min_window_sec and slices[-2][1] >= e_last:
                slices.pop()

    out: List[Dict[str, Any]] = []
    for s_idx, e_idx in slices:
        seg = wav[s_idx:e_idx]
        if len(seg) < int(min_window_sec * sr):
            continue
        emb = _encode_audio_segment(seg, model, processor)
        out.append({
            "start_sec": round(s_idx / sr, 2),
            "end_sec": round(e_idx / sr, 2),
            "embedding": emb,
        })
    return out


def encode_text_for_audio(text: str) -> List[float]:
    """Text → PE-AV audio space (via audio_model.text_audio_head)."""
    model, _ = _load_av()
    cls = _av_text_features(text)
    with torch.inference_mode():
        feat = model.audio_model.text_audio_head(cls)
        feat = _normalize(feat[0])
    return _to_float_list(feat)


def encode_video(video_bytes: bytes, ext: str = ".mp4") -> List[float]:
    """Video → PE-AV video space (single global embedding for the whole clip).

    Kept for backward compatibility and the search-by-video query path. For
    indexing long videos, prefer ``encode_video_windows``.
    """
    frames = _decode_video_frames(video_bytes, ext)
    return _encode_video_frames(frames)


def _encode_video_frames(frames: np.ndarray) -> List[float]:
    """Embed an already-sampled (T,H,W,3) uint8 frame stack into PE-AV video space."""
    model, processor = _load_av()
    inputs = processor(videos=[frames], return_tensors="pt")
    dtype = _resolve_dtype()
    inputs = {
        k: (v.to(_get_device(), dtype=dtype) if hasattr(v, "to") and v.dtype.is_floating_point
            else (v.to(_get_device()) if hasattr(v, "to") else v))
        for k, v in inputs.items()
    }
    with torch.inference_mode():
        # transformers main has a bug where PeAudioVideoModel.get_video_embeds
        # delegates to a missing PeVideoModel.get_video_embeds; go through the
        # encoder + head directly (same as PeVideoModel.forward).
        vm = model.video_model
        video_outputs = vm.video_encoder(pixel_values_videos=inputs["pixel_values_videos"])
        feat = vm.video_head(video_outputs.pooler_output)
        feat = _normalize(feat[0])
    return _to_float_list(feat)


def encode_video_windows(
    video_bytes: bytes,
    ext: str = ".mp4",
    window_sec: float = 10.0,
    overlap_sec: float = 2.0,
    frames_per_window: int = 8,
) -> List[Dict[str, Any]]:
    """Sliding-window video embeddings.

    Splits the video into overlapping time windows (default 10s with 2s
    overlap → stride 8s) and embeds each window's uniformly-sampled frames
    into PE-AV video space. Short clips (≤window_sec) yield a single window.

    Returns: [{"start_sec": float, "end_sec": float, "embedding": [..]}, ...]
    """
    import av

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
        f.write(video_bytes)
        path = f.name
    try:
        container = av.open(path)
        # Pull all frames with their timestamps
        stream = container.streams.video[0]
        time_base = float(stream.time_base) if stream.time_base else 1.0 / 30.0
        frames: List[np.ndarray] = []
        timestamps: List[float] = []
        for frame in container.decode(video=0):
            frames.append(frame.to_ndarray(format="rgb24"))
            ts = float(frame.pts) * time_base if frame.pts is not None else len(frames) * time_base
            timestamps.append(ts)
        container.close()
    finally:
        os.unlink(path)

    if not frames:
        raise ValueError("video contained no decodable frames")

    duration = timestamps[-1] if timestamps else 0.0
    stride = window_sec - overlap_sec
    if stride <= 0:
        raise ValueError("overlap_sec must be < window_sec")

    if duration <= window_sec:
        windows = [(0.0, duration)]
    else:
        windows = []
        start = 0.0
        while start < duration:
            end = min(start + window_sec, duration)
            windows.append((start, end))
            if end >= duration:
                break
            start += stride

    out: List[Dict[str, Any]] = []
    for s_sec, e_sec in windows:
        # Find frames whose timestamps fall in [s_sec, e_sec]
        idxs = [i for i, t in enumerate(timestamps) if s_sec <= t <= e_sec]
        if not idxs:
            continue
        # Uniformly subsample to frames_per_window
        if len(idxs) > frames_per_window:
            pick = np.linspace(0, len(idxs) - 1, frames_per_window).astype(int)
            idxs = [idxs[i] for i in pick]
        clip = np.stack([frames[i] for i in idxs])
        emb = _encode_video_frames(clip)
        out.append({
            "start_sec": round(s_sec, 2),
            "end_sec": round(e_sec, 2),
            "embedding": emb,
        })
    return out


def encode_text_for_video(text: str) -> List[float]:
    """Text → PE-AV video space (via video_model.text_video_head)."""
    model, _ = _load_av()
    cls = _av_text_features(text)
    with torch.inference_mode():
        feat = model.video_model.text_video_head(cls)
        feat = _normalize(feat[0])
    return _to_float_list(feat)


def _decode_video_frames(video_bytes: bytes, ext: str = ".mp4", num_frames: int = 8) -> np.ndarray:
    """Sample N uniformly-spaced RGB frames from a video → (T, H, W, 3) uint8."""
    import av

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
        f.write(video_bytes)
        path = f.name
    try:
        container = av.open(path)
        frames = [f.to_ndarray(format="rgb24") for f in container.decode(video=0)]
        if not frames:
            raise ValueError("Video contained no decodable frames")
        idx = np.linspace(0, len(frames) - 1, num_frames).astype(int)
        return np.stack([frames[i] for i in idx])
    finally:
        os.unlink(path)


# ── Convenience: encode text into all 3 spaces (for indexing text chunks) ───

def encode_text_all(text: str) -> Dict[str, List[float]]:
    """Encode text into image/audio/video spaces. Used when indexing text chunks."""
    return {
        "image": encode_text_for_image(text),
        "audio": encode_text_for_audio(text),
        "video": encode_text_for_video(text),
    }


# ── Batched encoders ────────────────────────────────────────────
#
# Each batched function chunks its input into sub-batches of `batch_size`
# to bound peak GPU/MPS memory, then runs one forward pass per sub-batch.
# All outputs are L2-normalized per row, mirroring the single-item encoders.

def _batch_to_lists(t: torch.Tensor) -> List[List[float]]:
    """Cast batched device tensor → list-of-fp32-lists (public API contract)."""
    return t.detach().to(dtype=torch.float32, device="cpu").tolist()


def encode_text_for_image_batch(texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """Batched: texts → PE-Core text space (alignable with images)."""
    if not texts:
        return []
    model, _, tok = _load_core()
    device = _get_device()
    out: List[List[float]] = []
    for i in range(0, len(texts), batch_size):
        sub = texts[i : i + batch_size]
        tokens = tok(sub).to(device)
        with torch.inference_mode():
            feats = model.encode_text(tokens)
            feats = _normalize(feats)
        out.extend(_batch_to_lists(feats))
    return out


def encode_text_for_audio_batch(texts: List[str], batch_size: int = 16) -> List[List[float]]:
    """Batched: texts → PE-AV audio text space (via audio_model.text_audio_head)."""
    if not texts:
        return []
    model, _ = _load_av()
    out: List[List[float]] = []
    for i in range(0, len(texts), batch_size):
        sub = texts[i : i + batch_size]
        with torch.inference_mode():
            cls = _av_text_features_batch(sub)            # (n, 1024) one matmul
            feats = model.audio_model.text_audio_head(cls)  # (n, 1024) one matmul
            feats = _normalize(feats)
        out.extend(_batch_to_lists(feats))
    return out


def encode_text_for_video_batch(texts: List[str], batch_size: int = 16) -> List[List[float]]:
    """Batched: texts → PE-AV video text space (via video_model.text_video_head)."""
    if not texts:
        return []
    model, _ = _load_av()
    out: List[List[float]] = []
    for i in range(0, len(texts), batch_size):
        sub = texts[i : i + batch_size]
        with torch.inference_mode():
            cls = _av_text_features_batch(sub)
            feats = model.video_model.text_video_head(cls)
            feats = _normalize(feats)
        out.extend(_batch_to_lists(feats))
    return out


def encode_text_all_batch(texts: List[str]) -> List[Dict[str, List[float]]]:
    """Batched per-space embeddings for many texts (used when indexing chunks).

    Runs each of the 3 encoders once over the full list (with internal
    sub-batching), then transposes back to per-text dicts.
    """
    if not texts:
        return []
    image_vecs = encode_text_for_image_batch(texts)
    audio_vecs = encode_text_for_audio_batch(texts)
    video_vecs = encode_text_for_video_batch(texts)
    return [
        {"image": image_vecs[i], "audio": audio_vecs[i], "video": video_vecs[i]}
        for i in range(len(texts))
    ]


def encode_image_batch(image_bytes_list: List[bytes], batch_size: int = 16) -> List[List[float]]:
    """Batched: images → PE-Core image space."""
    if not image_bytes_list:
        return []
    model, preprocess, _ = _load_core()
    device = _get_device()
    dtype = _resolve_dtype()
    out: List[List[float]] = []
    for i in range(0, len(image_bytes_list), batch_size):
        sub = image_bytes_list[i : i + batch_size]
        tensors = []
        for b in sub:
            img = Image.open(io.BytesIO(b)).convert("RGB")
            tensors.append(preprocess(img))
        batch = torch.stack(tensors, dim=0).to(device=device, dtype=dtype)
        with torch.inference_mode():
            feats = model.encode_image(batch)
            feats = _normalize(feats)
        out.extend(_batch_to_lists(feats))
    return out
