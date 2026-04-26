"""
MiniCPM-o-4.5 image/keyframe captioner via llama-server.

Why this exists
---------------
BLIP-base captions photorealistically and never produces style descriptors
("animated", "cartoon", "watercolor"). On video keyframes from animated
content, it blurs the entire genre signal — see the Big Buck Bunny eval
result. MiniCPM-o-4.5 (a 9B vision-speech-text MLLM) produces richer,
style-aware captions and benchmarks at GPT-4o-202405 level on
single-image understanding.

Implementation
--------------
We do NOT load llama.cpp into our Python process. Instead, on first use we
spawn the standalone `llama-server` binary (installed via `brew install
llama.cpp`) as a subprocess pointed at MiniCPM-o-4.5-Q4_0.gguf + the
vision projector. We then talk to its OpenAI-compatible
`/v1/chat/completions` endpoint over localhost HTTP.

This is deliberate:
  - llama-cpp-python's multimodal handlers are flaky and not always in
    sync with new GGUF families.
  - llama-server is the canonical, well-tested multimodal path.
  - Subprocess isolation means a captioner OOM does NOT take down the
    FastAPI process.
  - We can swap models or quantizations by changing env vars without
    touching code.

Activation
----------
Set CAPTIONER=minicpm in the environment. Default is BLIP.
On startup, files must exist at MINICPM_MODEL_PATH and MINICPM_MMPROJ_PATH
(defaults under ~/.cache/embed-models/).

Cost notes
----------
Q4_0 = 4.77 GB on disk, ~5–6 GB RAM at runtime with default context.
We use n_ctx=2048 (small) since captions are short — saves KV cache memory.
Each caption is one forward pass: ~500 ms on M-series Metal.
"""
from __future__ import annotations

import atexit
import base64
import os
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

import httpx

from app.core.logger import app_logger as logger


# ── Configuration ─────────────────────────────────────────────────

DEFAULT_MODEL_DIR = Path.home() / ".cache" / "embed-models"

MODEL_PATH = Path(
    os.environ.get("MINICPM_MODEL_PATH",
                   DEFAULT_MODEL_DIR / "MiniCPM-o-4_5-Q4_0.gguf")
)
MMPROJ_PATH = Path(
    os.environ.get("MINICPM_MMPROJ_PATH",
                   DEFAULT_MODEL_DIR / "vision" / "MiniCPM-o-4_5-vision-F16.gguf")
)

# Small context — captions are <100 tokens, no need for a 4k+ KV cache.
CONTEXT_SIZE = int(os.environ.get("MINICPM_CTX", "2048"))
PORT = int(os.environ.get("MINICPM_PORT", "8082"))
HOST = os.environ.get("MINICPM_HOST", "127.0.0.1")
# -ngl 99 → push everything to Metal/CUDA; llama.cpp clamps to actual layer count.
N_GPU_LAYERS = int(os.environ.get("MINICPM_NGL", "99"))
STARTUP_TIMEOUT = float(os.environ.get("MINICPM_STARTUP_TIMEOUT", "180"))
REQUEST_TIMEOUT = float(os.environ.get("MINICPM_REQ_TIMEOUT", "60"))


# ── Subprocess lifecycle ──────────────────────────────────────────

_proc: Optional[subprocess.Popen] = None
_lock = threading.Lock()
_available = True   # flips False if startup raises
_base_url = f"http://{HOST}:{PORT}"


def _llama_server_binary() -> Optional[str]:
    return shutil.which("llama-server")


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _start_server() -> bool:
    """Lazy-start llama-server. Idempotent; returns True if running."""
    global _proc, _available

    if not _available:
        return False
    if _proc is not None and _proc.poll() is None:
        return True

    binary = _llama_server_binary()
    if not binary:
        logger.warning(
            "MiniCPM captioner: `llama-server` not found on PATH. "
            "Install with `brew install llama.cpp` (macOS) or build from "
            "ggml-org/llama.cpp. Falling back to BLIP."
        )
        _available = False
        return False

    if not MODEL_PATH.exists() or not MMPROJ_PATH.exists():
        logger.warning(
            f"MiniCPM captioner: model files missing at {MODEL_PATH} or "
            f"{MMPROJ_PATH}. Falling back to BLIP."
        )
        _available = False
        return False

    if _port_open(HOST, PORT, 0.2):
        # An existing llama-server is already on the port — assume it's ours.
        logger.info(f"MiniCPM captioner: existing server on {HOST}:{PORT} — reusing")
        return True

    cmd = [
        binary,
        "-m", str(MODEL_PATH),
        "--mmproj", str(MMPROJ_PATH),
        "-c", str(CONTEXT_SIZE),
        "-ngl", str(N_GPU_LAYERS),
        "--host", HOST,
        "--port", str(PORT),
        "--log-disable",
    ]
    logger.info(f"MiniCPM captioner: starting llama-server "
                f"(ctx={CONTEXT_SIZE}, ngl={N_GPU_LAYERS}, port={PORT})")
    try:
        _proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as e:
        logger.warning(f"MiniCPM captioner: failed to spawn llama-server: {e}")
        _available = False
        return False

    # Wait for /health to flip ready
    deadline = time.monotonic() + STARTUP_TIMEOUT
    while time.monotonic() < deadline:
        if _proc.poll() is not None:
            logger.warning(
                f"MiniCPM captioner: llama-server exited early "
                f"(rc={_proc.returncode}). Falling back to BLIP."
            )
            _available = False
            _proc = None
            return False
        try:
            r = httpx.get(f"{_base_url}/health", timeout=2)
            if r.status_code == 200:
                logger.info(f"MiniCPM captioner: ready at {_base_url}")
                return True
        except httpx.HTTPError:
            pass
        time.sleep(1)

    logger.warning(f"MiniCPM captioner: server did not become healthy within "
                   f"{STARTUP_TIMEOUT}s — falling back to BLIP")
    _stop_server()
    _available = False
    return False


def _stop_server() -> None:
    global _proc
    if _proc is None:
        return
    try:
        _proc.terminate()
        try:
            _proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _proc.kill()
            _proc.wait(timeout=2)
    except Exception as e:
        logger.warning(f"MiniCPM captioner: error stopping server: {e}")
    finally:
        _proc = None


atexit.register(_stop_server)


# ── Public API ────────────────────────────────────────────────────

def is_available() -> bool:
    return _available and (_proc is None or _proc.poll() is None) and _llama_server_binary() is not None


def shutdown() -> None:
    """Stop the llama-server subprocess. Called from FastAPI lifespan shutdown."""
    _stop_server()


_PROMPT = (
    "Describe what is shown in this image in one short sentence. "
    "If it is animated, illustrated, drawn, or stylized, say so explicitly."
)


def caption_image(image_bytes: bytes, prompt: str = _PROMPT) -> Optional[str]:
    """Return a short caption for the image, or None on failure.

    Style-aware: the prompt explicitly asks the model to flag animation /
    illustration / stylization, which fixes BLIP's blind spot for cartoons.
    """
    with _lock:
        if not _start_server():
            return None

    # Detect format from magic bytes; MiniCPM/llama-server accepts PNG/JPEG/WebP.
    if image_bytes.startswith(b"\x89PNG"):
        mime = "image/png"
    elif image_bytes.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        mime = "image/webp"
    else:
        mime = "image/png"  # conservative default
    b64 = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "model": "minicpm-o-4.5",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url",
                 "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ],
        }],
        "temperature": 0.2,
        "max_tokens": 100,
        # MiniCPM-o-4.5 ships with thinking mode on by default — that
        # blows past max_tokens before any visible content lands. Disable
        # it for caption use; we want the answer, not the reasoning trace.
        "chat_template_kwargs": {"enable_thinking": False},
    }
    try:
        r = httpx.post(f"{_base_url}/v1/chat/completions",
                       json=payload, timeout=REQUEST_TIMEOUT)
    except httpx.HTTPError as e:
        logger.warning(f"MiniCPM captioner request failed: {e}")
        return None
    if r.status_code != 200:
        logger.warning(f"MiniCPM captioner: HTTP {r.status_code} — {r.text[:200]}")
        return None
    try:
        choice = r.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        logger.warning(f"MiniCPM captioner: malformed response: {e}")
        return None
    return choice.strip() or None
