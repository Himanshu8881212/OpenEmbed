"""
In-memory BM25 indexes per vault for hybrid keyword retrieval.
Built lazily on first query, rebuilt when indexing adds rows.
"""
import re
import threading
from typing import Dict, List, Optional, Tuple

from rank_bm25 import BM25Okapi

from app.core.logger import app_logger as logger

# vault_name → {"bm25": BM25Okapi, "chunks": List[(chunk_id, text, metadata)], "stale": bool}
_indexes: Dict[str, dict] = {}
_lock = threading.RLock()

# Split on anything that isn't a letter or digit. Importantly this splits
# `eiffel_tower.jpg` → ["eiffel", "tower", "jpg"] and `co2-emissions` →
# ["co2", "emissions"], which simple `\w+` (which keeps underscores) does not.
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+", re.UNICODE)

# Conservative English stopword set. Without this, queries like "iron lattice
# tower in paris" matched any chunk containing "in" — which is every speech
# transcript — and BM25 normalization promoted those to similarity 1.0 even
# when no content word matched. Keeping the list small to avoid hurting
# legitimate matches in non-English vaults; expand later if needed.
_STOPWORDS = frozenset({
    "a", "an", "and", "or", "the", "of", "in", "on", "at", "to", "for",
    "with", "by", "from", "as", "is", "are", "was", "were", "be", "been",
    "being", "this", "that", "these", "those", "it", "its", "i", "me",
    "my", "we", "our", "you", "your", "he", "him", "his", "she", "her",
    "they", "them", "their", "what", "which", "who", "whom", "whose",
    "do", "does", "did", "have", "has", "had", "can", "could", "will",
    "would", "should", "may", "might", "must", "shall", "not", "no",
})


def _tokenize(text: str) -> List[str]:
    out = []
    for w in _TOKEN_RE.findall(text or ""):
        wl = w.lower()
        if len(wl) <= 1:
            continue
        if wl in _STOPWORDS:
            continue
        out.append(wl)
    return out


def mark_stale(vault: str) -> None:
    """Call when chunks change so the index gets rebuilt on next query."""
    with _lock:
        if vault in _indexes:
            _indexes[vault]["stale"] = True


def reset(vault: Optional[str] = None) -> None:
    """Wipe one vault's index, or all if vault is None."""
    with _lock:
        if vault is None:
            _indexes.clear()
        else:
            _indexes.pop(vault, None)


def _rebuild(vault: str, chunks: List[Tuple[str, str, dict]]) -> None:
    """chunks = [(chunk_id, text, metadata), ...]"""
    if not chunks:
        _indexes[vault] = {"bm25": None, "chunks": [], "stale": False}
        return
    tokenized = [_tokenize(text) for _, text, _ in chunks]
    _indexes[vault] = {
        "bm25": BM25Okapi(tokenized),
        "chunks": chunks,
        "stale": False,
    }
    logger.info(f"BM25 rebuilt for {vault}: {len(chunks)} chunks")


def search(
    vault: str,
    query: str,
    chunks_provider,
    n_results: int = 50,
) -> List[dict]:
    """
    Lexical BM25 search over a vault's chunks.
    chunks_provider: callable(vault) -> List[(chunk_id, text, metadata)] used to (re)build.
    Returns hits in the same shape as chroma's search_space().
    """
    with _lock:
        idx = _indexes.get(vault)
        if idx is None or idx.get("stale"):
            _rebuild(vault, chunks_provider(vault))
            idx = _indexes[vault]

    bm25 = idx["bm25"]
    chunks = idx["chunks"]
    if bm25 is None or not chunks:
        return []

    tokens = _tokenize(query)
    if not tokens:
        return []

    scores = bm25.get_scores(tokens)
    if not len(scores):
        return []

    # rank by score
    top = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n_results]
    max_score = max(scores) or 1.0

    items: List[dict] = []
    for i in top:
        if scores[i] <= 0:
            break
        cid, text, meta = chunks[i]
        items.append({
            "id": cid,
            "similarity": round(float(scores[i] / max_score), 4),  # normalize to [0,1] for downstream merging
            "bm25_score": round(float(scores[i]), 4),
            "metadata": meta,
            "document": text,
        })
    return items
