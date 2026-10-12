"""Self-hosted EmbeddingGemma 2 inference service (internal; the public contract lives in the Next.js API).

POST /embed {"profile": {model, revision, dtype}, "inputs": [{"parts": [{type, text | data_b64}]}]}
 -> {"data": [{"embedding": [...768 floats], "tokens": int}], "model", "revision", "dtype"}
Callers apply prompts. The service measures tokens, enforces the context budget (no silent truncation),
rejects non-finite vectors and re-normalizes in float32.
"""
import base64
import os
import tempfile
import threading
import time

import numpy as np
import torch
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer
from sentence_transformers.util import batch_to_device

MODEL = os.environ.get("KB_MODEL", "google/embeddinggemma-2")
REVISION = os.environ.get("KB_MODEL_REVISION", "914f7f89142e33e77833254d9c9b90c3cef7303b")
DTYPE = os.environ.get("KB_INFERENCE_DTYPE", "float32")
def _pick_device(want: str) -> str:
    """auto: CUDA, else Apple GPU (MPS), else CPU. Device is not part of profile identity; the equivalence gate below
    proves the vectors match the CPU float32 reference before the service accepts work."""
    if want != "auto":
        return want
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


DEVICE = _pick_device(os.environ.get("KB_INFERENCE_DEVICE", "auto"))
EQUIVALENCE_MIN_COSINE = float(os.environ.get("KB_EQUIVALENCE_MIN_COSINE", "0.9999"))
TOKEN = os.environ.get("KB_INFERENCE_TOKEN", "")
MAX_TOKENS = 8192
DIMS = 768
PLACEHOLDER = {"image": "<|image|>", "audio": "<|audio|>", "video": "<|video|>"}
SUFFIX = {"image": ".img", "audio": ".audio", "video": ".mp4"}

if DTYPE not in ("float32", "bfloat16"):
    raise SystemExit("KB_INFERENCE_DTYPE must be float32 or bfloat16 (float16 yields NaN for this model)")
if not TOKEN:
    raise SystemExit("KB_INFERENCE_TOKEN is required")

# ---- metrics (Prometheus text exposition, no client library needed)
BUCKETS = (0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60)
_m_lock = threading.Lock()
_requests: dict[tuple[str, str], int] = {}          # (modality, status) -> count
_inputs: dict[str, int] = {}                        # modality -> inputs embedded
_tokens: dict[str, int] = {}                        # modality -> model tokens processed
_hist: dict[str, list[float]] = {}                  # modality -> bucket counts..., +Inf, sum
_waiting = 0                                        # requests waiting for the model lock
_busy = 0                                           # 1 while a forward pass runs


def _observe(modality: str, seconds: float, inputs: int, tokens: int):
    with _m_lock:
        _inputs[modality] = _inputs.get(modality, 0) + inputs
        _tokens[modality] = _tokens.get(modality, 0) + tokens
        h = _hist.setdefault(modality, [0.0] * (len(BUCKETS) + 2))
        for i, le in enumerate(BUCKETS):
            if seconds <= le:
                h[i] += 1
        h[len(BUCKETS)] += 1
        h[len(BUCKETS) + 1] += seconds


def _count(modality: str, status: str):
    with _m_lock:
        _requests[(modality, status)] = _requests.get((modality, status), 0) + 1


_model: SentenceTransformer | None = None
_lock = threading.Lock()  # ponytail: one forward pass at a time per process; scale by running more processes.


def model() -> SentenceTransformer:
    global _model
    if _model is None:
        m = SentenceTransformer(MODEL, revision=REVISION, device=DEVICE, model_kwargs={"torch_dtype": getattr(torch, DTYPE)})
        m.eval()
        _equivalence_gate(m)
        _model = m
    return _model


EQUIVALENCE: dict = {}


def _equivalence_gate(m: SentenceTransformer):
    """Refuse to serve if this device/precision produces vectors that differ from the CPU float32 reference."""
    import io, json
    from PIL import Image
    ref = json.load(open(os.path.join(os.path.dirname(__file__), "probe_reference.json")))
    if (ref["model"], ref["revision"], ref["dtype"]) != (MODEL, REVISION, DTYPE):
        EQUIVALENCE.update(status="skipped", reason="reference is for another model/revision/dtype")
        return
    img = Image.open(io.BytesIO(base64.b64decode(ref["probes"]["image_png_b64"]))).convert("RGB")
    with torch.inference_mode():
        got = {"text": m.encode([ref["probes"]["text"]])[0], "image": m.encode([{"image": img}])[0]}
    cos = {k: float(np.dot(got[k], ref["vectors"][k]) / (np.linalg.norm(got[k]) * np.linalg.norm(ref["vectors"][k]))) for k in got}
    EQUIVALENCE.update(status="ok" if min(cos.values()) >= EQUIVALENCE_MIN_COSINE else "failed", cosine={k: round(v, 7) for k, v in cos.items()}, device=DEVICE)
    if EQUIVALENCE["status"] != "ok":
        raise SystemExit(f"device {DEVICE} fails the equivalence gate (cosine {cos}); set KB_INFERENCE_DEVICE=cpu")


class Part(BaseModel):
    type: str = Field(pattern="^(text|image|audio|video)$")
    text: str | None = None
    data_b64: str | None = None


class Input(BaseModel):
    parts: list[Part] = Field(min_length=1, max_length=64)


class Profile(BaseModel):
    model: str
    revision: str
    dtype: str


class Processing(BaseModel):
    max_soft_tokens: int | None = Field(default=None)


class EmbedRequest(BaseModel):
    profile: Profile
    inputs: list[Input] = Field(min_length=1, max_length=256)
    processing: dict[str, Processing] = Field(default_factory=dict)  # e.g. {"video": {"max_soft_tokens": 280}} from the profile


class InputError(Exception):
    def __init__(self, index: int, code: str, message: str):
        self.index, self.code, self.message = index, code, message


def _to_st_input(inp: Input, tmp: str, i: int):
    """Interleave parts in order: text with media placeholders, media lists in the same order."""
    if len(inp.parts) == 1 and inp.parts[0].type == "text":
        if inp.parts[0].text is None:
            raise InputError(i, "INVALID_REQUEST", "text part requires text")
        return inp.parts[0].text
    text, media = [], {"image": [], "audio": [], "video": []}
    for j, p in enumerate(inp.parts):
        if p.type == "text":
            if p.text is None:
                raise InputError(i, "INVALID_REQUEST", "text part requires text")
            text.append(p.text)
            continue
        if not p.data_b64:
            raise InputError(i, "INVALID_REQUEST", f"{p.type} part requires data_b64")
        path = os.path.join(tmp, f"{i}_{j}{SUFFIX[p.type]}")
        with open(path, "wb") as f:
            f.write(base64.b64decode(p.data_b64, validate=True))
        if p.type == "image":
            from PIL import Image
            try:
                media["image"].append(Image.open(path).convert("RGB"))
            except Exception:
                raise InputError(i, "FORMAT_UNSUPPORTED", "image could not be decoded")
        else:
            media[p.type].append(path)
        text.append(PLACEHOLDER[p.type])
    out = {"text": " ".join(text)}
    for k, v in media.items():
        if v:
            out[k] = v
    return out


def embed(req: EmbedRequest) -> list[dict]:
    if (req.profile.model, req.profile.revision, req.profile.dtype) != (MODEL, REVISION, DTYPE):
        raise HTTPException(409, {"code": "PROFILE_UNAVAILABLE", "message": "this inference host does not serve the requested profile"})
    m = model()
    results: list[dict] = [None] * len(req.inputs)  # type: ignore
    with tempfile.TemporaryDirectory() as tmp:
        st_inputs = [_to_st_input(inp, tmp, i) for i, inp in enumerate(req.inputs)]
        # text-only inputs batch together; media inputs go one at a time (different feature keys)
        groups = [[i for i, x in enumerate(st_inputs) if isinstance(x, str)]] + \
                 [[i] for i, x in enumerate(st_inputs) if not isinstance(x, str)]
        global _waiting, _busy
        with _m_lock:
            _waiting += 1
        _lock.acquire()
        with _m_lock:
            _waiting -= 1
            _busy = 1
        try:
          with torch.inference_mode():
            for idx in groups:
                if not idx:
                    continue
                started = time.perf_counter()
                modality = "text" if isinstance(st_inputs[idx[0]], str) else "+".join(sorted(k for k in ("image", "audio", "video") if k in st_inputs[idx[0]])) or "text"
                pk = {k: {"max_soft_tokens": v.max_soft_tokens} for k, v in req.processing.items()
                      if k in ("image", "video") and v.max_soft_tokens in (70, 140, 280, 560, 1120) and k in str(modality)}
                try:
                    feats = m.preprocess([st_inputs[i] for i in idx], **({"processing_kwargs": pk} if pk else {}))
                except Exception as e:  # decoder/codec failure
                    raise InputError(idx[0], "FORMAT_UNSUPPORTED", f"input could not be decoded: {type(e).__name__}")
                tokens = feats["attention_mask"].sum(dim=1).tolist()
                for i, t in zip(idx, tokens):
                    if t > MAX_TOKENS:
                        raise InputError(i, "INPUT_TOO_LARGE", f"input uses {t} tokens; limit is {MAX_TOKENS}")
                out = m(batch_to_device(feats, m.device))["sentence_embedding"].float().cpu().numpy()
                for i, t, v in zip(idx, tokens, out):
                    if v.shape != (DIMS,) or not np.isfinite(v).all():
                        raise HTTPException(500, {"code": "NON_FINITE_EMBEDDING", "message": "model produced an invalid vector"})
                    n = float(np.linalg.norm(v))
                    if n == 0:
                        raise HTTPException(500, {"code": "NON_FINITE_EMBEDDING", "message": "zero vector"})
                    results[i] = {"embedding": (v / n).astype(np.float32).tolist(), "tokens": int(t)}
                _observe(modality, time.perf_counter() - started, len(idx), int(sum(tokens)))
        finally:
            with _m_lock:
                _busy = 0
            _lock.release()
    return results


app = FastAPI(title="kb-inference", docs_url=None, redoc_url=None)


def _auth(authorization: str | None):
    if authorization != f"Bearer {TOKEN}":
        raise HTTPException(401, {"code": "AUTHENTICATION_REQUIRED", "message": "invalid inference token"})


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/readyz")
def readyz():
    model()
    return {"ok": True, "model": MODEL, "revision": REVISION, "dtype": DTYPE, "device": DEVICE, "dims": DIMS, "max_tokens": MAX_TOKENS, "equivalence": EQUIVALENCE}


@app.get("/metrics")
def metrics(authorization: str | None = Header(default=None)):
    """Prometheus metrics (Authorization: Bearer $KB_METRICS_TOKEN). No inputs or content are recorded."""
    from fastapi.responses import PlainTextResponse
    want = os.environ.get("KB_METRICS_TOKEN", "")
    if not want or authorization != f"Bearer {want}":
        raise HTTPException(404)
    out = ["# TYPE kb_inference_requests_total counter"]
    with _m_lock:
        out += [f'kb_inference_requests_total{{modality="{m}",status="{s}"}} {v}' for (m, s), v in _requests.items()]
        out += ["# TYPE kb_inference_inputs_total counter"] + [f'kb_inference_inputs_total{{modality="{m}"}} {v}' for m, v in _inputs.items()]
        out += ["# TYPE kb_inference_tokens_total counter"] + [f'kb_inference_tokens_total{{modality="{m}"}} {v}' for m, v in _tokens.items()]
        out.append("# TYPE kb_inference_seconds histogram")
        for m, h in _hist.items():
            out += [f'kb_inference_seconds_bucket{{modality="{m}",le="{le}"}} {int(h[i])}' for i, le in enumerate(BUCKETS)]
            out += [f'kb_inference_seconds_bucket{{modality="{m}",le="+Inf"}} {int(h[len(BUCKETS)])}', f'kb_inference_seconds_count{{modality="{m}"}} {int(h[len(BUCKETS)])}', f'kb_inference_seconds_sum{{modality="{m}"}} {h[len(BUCKETS) + 1]:.6f}']
        out += ["# TYPE kb_inference_waiting gauge", f"kb_inference_waiting {_waiting}", "# TYPE kb_inference_busy gauge", f"kb_inference_busy {_busy}",
                "# TYPE kb_inference_model_info gauge", f'kb_inference_model_info{{model="{MODEL}",revision="{REVISION[:7]}",dtype="{DTYPE}",device="{DEVICE}"}} 1']
    return PlainTextResponse("\n".join(out) + "\n", media_type="text/plain; version=0.0.4")


@app.post("/embed")
def embed_route(req: EmbedRequest, authorization: str | None = Header(default=None)):
    _auth(authorization)
    kind = "+".join(sorted({p.type for i in req.inputs for p in i.parts}))
    try:
        data = embed(req)
        _count(kind, "ok")
    except InputError as e:
        _count(kind, e.code.lower())
        raise HTTPException(413 if e.code == "INPUT_TOO_LARGE" else 400 if e.code == "INVALID_REQUEST" else 415,
                            {"code": e.code, "message": e.message, "index": e.index})
    return {"data": data, "model": MODEL, "revision": REVISION, "dtype": DTYPE}


@app.exception_handler(Exception)
async def _unhandled(request, exc):  # count unexpected failures, never leak details
    from fastapi.responses import JSONResponse
    _count("unknown", "error")
    return JSONResponse({"detail": {"code": "INTERNAL_ERROR", "message": "inference failed"}}, status_code=500)


if __name__ == "__main__":
    import uvicorn
    model()  # load before accepting traffic
    uvicorn.run(app, host=os.environ.get("KB_INFERENCE_HOST", "127.0.0.1"), port=int(os.environ.get("KB_INFERENCE_PORT", "8100")), log_level="warning")
