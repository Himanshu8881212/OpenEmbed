"""
Cross-encoder reranker (BGE-reranker-v2-m3) — sharper top-K than bi-encoders.
Lazy-loaded on first use, runs on M3 MPS in fp16.
"""
import os
from typing import List, Optional, Tuple

import torch

from app.core.logger import app_logger as logger

_model = None
_tokenizer = None
_device: Optional[torch.device] = None


def _get_device() -> torch.device:
    global _device
    if _device is None:
        if torch.backends.mps.is_available():
            _device = torch.device("mps")
        elif torch.cuda.is_available():
            _device = torch.device("cuda")
        else:
            _device = torch.device("cpu")
    return _device


def _load():
    global _model, _tokenizer
    if _model is None:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        ckpt = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
        device = _get_device()
        logger.info(f"Loading reranker {ckpt}...")
        _tokenizer = AutoTokenizer.from_pretrained(ckpt)
        try:
            _model = AutoModelForSequenceClassification.from_pretrained(ckpt, torch_dtype=torch.float16)
        except Exception:
            _model = AutoModelForSequenceClassification.from_pretrained(ckpt)
        _model = _model.to(device).eval()
        logger.info("Reranker ready")
    return _model, _tokenizer


def initialize() -> bool:
    try:
        _load()
        # Warmup with a realistic query/document pair so the first real
        # request doesn't pay the kernel-compile cost. Includes both a
        # short and a long document to prime padding shapes.
        score(
            ["What is the capital of France?"],
            [[
                "Paris is the capital and most populous city of France.",
                "The Eiffel Tower stands 330 metres tall along the Seine in Paris, and was "
                "completed in 1889 for the Exposition Universelle.",
            ]],
        )
        return True
    except Exception as e:
        logger.error(f"Reranker init failed: {e}")
        return False


def is_ready() -> bool:
    return _model is not None


def score(queries: List[str], documents_per_query: List[List[str]], batch_size: int = 32) -> List[List[float]]:
    """
    For each query and its candidate documents, return relevance scores.
    Returns: List of score lists, one per query.
    """
    model, tok = _load()
    device = _get_device()
    out: List[List[float]] = []
    for q, docs in zip(queries, documents_per_query):
        if not docs:
            out.append([])
            continue
        scores: List[float] = []
        for i in range(0, len(docs), batch_size):
            batch = docs[i:i + batch_size]
            pairs = [(q, d) for d in batch]
            inputs = tok(
                [p[0] for p in pairs],
                [p[1] for p in pairs],
                padding=True, truncation=True, max_length=512, return_tensors="pt",
            ).to(device)
            with torch.inference_mode():
                logits = model(**inputs).logits.view(-1).float().cpu().tolist()
            scores.extend(logits)
        out.append(scores)
    return out


def rerank(query: str, hits: List[dict], top_k: int = 10) -> List[dict]:
    """
    Re-score hits with the cross-encoder, sort, return top_k.
    Mutates each hit in-place to add `rerank_score`.
    """
    if not hits:
        return []
    docs = [h.get("document") or "" for h in hits]
    scores_per_query = score([query], [docs])
    scores = scores_per_query[0] if scores_per_query else []
    for h, s in zip(hits, scores):
        h["rerank_score"] = round(float(s), 4)
    hits.sort(key=lambda h: h.get("rerank_score", 0.0), reverse=True)
    return hits[:top_k]
