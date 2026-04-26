"""
ChromaDB vector store service.

Each user-facing "vault" maps to THREE sub-collections internally:
    {vault}__image  — PE-Core image space (images + text-for-image)
    {vault}__audio  — PE-AV audio space   (audio + text-for-audio)
    {vault}__video  — PE-AV video space   (video + text-for-video)

The split is a hard requirement because PE-Core and PE-AV produce
embeddings in DIFFERENT vector spaces — mixing them in one collection
would make distance comparisons meaningless.
"""
from typing import Optional, List, Dict, Iterable
import chromadb

from app.core.config import settings
from app.core.logger import app_logger as logger


SPACES = ("image", "audio", "video")
_SEP = "__"
_client = None


def initialize() -> bool:
    global _client
    try:
        _client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        logger.info(f"ChromaDB initialized at {settings.chroma_persist_dir}")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize ChromaDB: {e}")
        return False


def is_ready() -> bool:
    return _client is not None


# ── Internal naming ──────────────────────────────────────────────

def _sub(vault: str, space: str) -> str:
    return f"{vault}{_SEP}{space}"


def _split(name: str) -> Optional[tuple]:
    """Return (vault, space) if name matches our sub-collection scheme."""
    if _SEP not in name:
        return None
    base, space = name.rsplit(_SEP, 1)
    if space not in SPACES:
        return None
    return base, space


# ── Vault lifecycle ─────────────────────────────────────────────

def create_collection(name: str, description: str = "", extra_metadata: Dict = None) -> Dict:
    """Create a vault — three sub-collections, one per embedding space."""
    meta = {"description": description or name}
    if extra_metadata:
        meta.update(extra_metadata)
    for space in SPACES:
        _client.get_or_create_collection(name=_sub(name, space), metadata={**meta, "space": space})
    return {"name": name, "count": 0, "metadata": meta}


def list_collections() -> List[Dict]:
    """List vaults (deduped from the 3 sub-collections per vault)."""
    by_vault: Dict[str, Dict] = {}
    for col in _client.list_collections():
        parts = _split(col.name)
        if not parts:
            continue
        vault, space = parts
        entry = by_vault.setdefault(vault, {"name": vault, "count": 0, "metadata": {}})
        entry["count"] += col.count()
        if not entry["metadata"]:
            meta = dict(col.metadata or {})
            meta.pop("api_key_hash", None)
            meta.pop("space", None)
            entry["metadata"] = meta
    return list(by_vault.values())


def get_collection(name: str) -> Optional[Dict]:
    """Get a vault with all its files (aggregated across spaces, deduplicated by doc_id)."""
    sub_cols = _existing_subs(name)
    if not sub_cols:
        return None

    total = 0
    seen_docs: Dict[str, Dict] = {}
    base_meta: Dict = {}

    for col in sub_cols:
        total += col.count()
        if not base_meta:
            base_meta = dict(col.metadata or {})
            base_meta.pop("api_key_hash", None)
            base_meta.pop("space", None)
        try:
            data = col.get(include=["metadatas"])
        except Exception:
            continue
        for i, meta in enumerate(data.get("metadatas") or []):
            doc_id = (meta or {}).get("doc_id") or data["ids"][i]
            if doc_id in seen_docs:
                continue
            seen_docs[doc_id] = {"id": data["ids"][i], "metadata": meta}

    return {
        "name": name,
        "count": total,
        "metadata": base_meta,
        "files": list(seen_docs.values()),
    }


def get_collection_metadata(name: str) -> Optional[Dict]:
    """Raw metadata (incl. api_key_hash) used for auth checks."""
    for col in _existing_subs(name):
        return dict(col.metadata or {})
    return None


def update_api_key_hash(vault: str, new_hash: str) -> bool:
    """Replace the api_key_hash on every sub-collection of a vault."""
    subs = _existing_subs(vault)
    if not subs:
        return False
    for col in subs:
        meta = dict(col.metadata or {})
        meta["api_key_hash"] = new_hash
        try:
            col.modify(metadata=meta)
        except Exception as e:
            logger.error(f"Failed to update api_key_hash on {col.name}: {e}")
            return False
    return True


def delete_collection(name: str) -> bool:
    """Delete all 3 sub-collections for a vault."""
    deleted_any = False
    for space in SPACES:
        try:
            _client.delete_collection(name=_sub(name, space))
            deleted_any = True
        except Exception:
            pass
    return deleted_any


def _existing_subs(vault: str):
    """Return the chroma collections for a vault that actually exist."""
    out = []
    for space in SPACES:
        try:
            out.append(_client.get_collection(name=_sub(vault, space)))
        except Exception:
            pass
    return out


# ── Writes ───────────────────────────────────────────────────────

def add_chunks(vault: str, space: str, chunks: List[Dict]) -> bool:
    """
    Add chunks to one sub-collection.
    Each chunk: {"id": str, "embedding": List[float], "metadata": Dict, "text": str}
    """
    if not chunks:
        return True
    if space not in SPACES:
        raise ValueError(f"Unknown space: {space}")
    try:
        col = _client.get_collection(name=_sub(vault, space))
        col.add(
            ids=[c["id"] for c in chunks],
            embeddings=[c["embedding"] for c in chunks],
            metadatas=[c["metadata"] for c in chunks],
            documents=[c["text"] for c in chunks],
        )
        # Invalidate the BM25 cache for this vault — rebuilt lazily on next query
        try:
            from app.services import bm25_service
            bm25_service.mark_stale(vault)
        except Exception:
            pass
        return True
    except Exception as e:
        logger.error(f"Failed to add chunks to {vault}/{space}: {e}")
        return False


def add_embedding(vault: str, space: str, doc_id: str, embedding: List[float], metadata: Dict) -> bool:
    """Add a single embedding to one sub-collection."""
    return add_chunks(vault, space, [{
        "id": doc_id,
        "embedding": embedding,
        "metadata": metadata,
        "text": _document_text_for_chunk(metadata, doc_id),
    }])


def _document_text_for_chunk(metadata: Dict, doc_id: str) -> str:
    """Best 'document text' to store with a chunk so the cross-encoder reranker
    and BM25 have meaningful content to score against.

    For image/audio/video chunks we don't have a transcript or extracted text,
    so we synthesize a humanized form from the filename:
        "eiffel_tower.jpg" + image → "image eiffel tower"

    Empirically, the bare keyword form scored best on the eval harness — full
    sentence-shaped captions ("A photograph showing eiffel tower.") *helped*
    the cross-encoder rank short docs against unrelated speech but introduced
    new false positives where the keyword "thunder" / "rain" started matching
    weather queries via sentence-form association. Keep it lean.
    """
    if "document_text" in metadata:
        return metadata["document_text"]

    filename = metadata.get("filename") or doc_id
    modality = (metadata.get("modality") or "").lower()

    # Split filename on `_-.` and whitespace; drop the trailing extension token
    import re as _re
    parts = [p.lower() for p in _re.split(r"[_\-\.\s]+", filename) if p]
    if parts and len(parts[-1]) <= 4:  # extension like 'jpg', 'webm', 'ogg'
        parts = parts[:-1]
    pretty = " ".join(parts) if parts else filename

    if modality and modality not in pretty:
        return f"{modality} {pretty}".strip()
    return pretty or filename


def delete_document(vault: str, doc_id: str) -> int:
    """Delete a parent document's chunks from all 3 sub-collections. Returns total count."""
    total = 0
    for col in _existing_subs(vault):
        try:
            existing = col.get(where={"doc_id": doc_id}, include=[])
            if existing["ids"]:
                col.delete(ids=existing["ids"])
                total += len(existing["ids"])
        except Exception as e:
            logger.error(f"Delete from {col.name} failed: {e}")
    if total:
        try:
            from app.services import bm25_service
            bm25_service.mark_stale(vault)
        except Exception:
            pass
    return total


# ── Searches ─────────────────────────────────────────────────────

def search_space(vault: str, space: str, embedding: List[float], n_results: int = 10,
                 min_similarity: float = 0.0, include_embeddings: bool = False,
                 where: Optional[Dict] = None) -> List[Dict]:
    """Query a single sub-collection (used for file-as-query searches)."""
    if space not in SPACES:
        raise ValueError(f"Unknown space: {space}")
    try:
        col = _client.get_collection(name=_sub(vault, space))
    except Exception:
        return []
    return _query_one(col, embedding, n_results, min_similarity, include_embeddings, where)


def search_all(
    vault: str,
    query_per_space: Dict[str, List[float]],
    n_results: int = 10,
    min_similarity: float = 0.0,
    pool_size: int = 50,
    use_rrf: bool = True,
    rrf_k: int = 60,
    include_embeddings: bool = False,
) -> List[Dict]:
    """
    Fan-out search across the 3 PE spaces. Default uses Reciprocal Rank Fusion
    so cross-modal hits aren't penalized by having lower raw cosine values.
    pool_size = how many to fetch per space before fusing.
    """
    per_space: Dict[str, List[Dict]] = {}
    for space, embed in query_per_space.items():
        if space not in SPACES:
            continue
        try:
            col = _client.get_collection(name=_sub(vault, space))
        except Exception:
            continue
        hits = _query_one(col, embed, pool_size, min_similarity, include_embeddings)
        for h in hits:
            h["space"] = space
        per_space[space] = hits

    if use_rrf:
        merged = _rrf_merge(per_space, rrf_k)
    else:
        merged = []
        for hits in per_space.values():
            merged.extend(hits)
        merged.sort(key=lambda h: h.get("similarity", 0), reverse=True)
        merged = _dedupe_by_id(merged)
    return merged[:n_results]


def search_space_pool(vault: str, space: str, embedding: List[float], n_results: int,
                      include_embeddings: bool = True, where: Optional[Dict] = None) -> List[Dict]:
    """Larger candidate pool for downstream MMR / reranking."""
    return search_space(vault, space, embedding, n_results, 0.0, include_embeddings, where=where)


def _query_one(col, embedding: List[float], n_results: int, min_similarity: float,
               include_embeddings: bool = False, where: Optional[Dict] = None) -> List[Dict]:
    count = col.count()
    if count == 0:
        return []
    include = ["metadatas", "distances", "documents"]
    if include_embeddings:
        include.append("embeddings")
    try:
        kwargs = {
            "query_embeddings": [embedding],
            "n_results": min(n_results, count),
            "include": include,
        }
        if where:
            kwargs["where"] = where
        results = col.query(**kwargs)
    except Exception as e:
        logger.error(f"Query on {col.name} failed: {e}")
        return []

    items: List[Dict] = []
    if not results or not results.get("ids") or not results["ids"][0]:
        return items
    embeds_row = (results.get("embeddings") or [None])[0] if include_embeddings else None
    for i, doc_id in enumerate(results["ids"][0]):
        distance = results["distances"][0][i] if results.get("distances") else 0
        similarity = max(0.0, 1.0 - distance / 2.0)
        if similarity >= min_similarity:
            item = {
                "id": doc_id,
                "similarity": round(similarity, 4),
                "distance": round(distance, 4),
                "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                "document": results["documents"][0][i] if results.get("documents") else "",
            }
            if embeds_row is not None:
                emb = embeds_row[i]
                item["embedding"] = list(emb) if emb is not None else None
            items.append(item)
    return items


def _rrf_merge(per_space: Dict[str, List[Dict]], k: int = 60) -> List[Dict]:
    """Reciprocal Rank Fusion across spaces — score = sum(1/(k+rank))."""
    scores: Dict[str, float] = {}
    items: Dict[str, Dict] = {}
    for space, hits in per_space.items():
        for rank, hit in enumerate(hits, start=1):
            cid = hit["id"]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
            existing = items.get(cid)
            if existing is None or hit.get("similarity", 0) > existing.get("similarity", 0):
                items[cid] = hit
    ordered = sorted(items.values(), key=lambda h: scores[h["id"]], reverse=True)
    for h in ordered:
        h["rrf_score"] = round(scores[h["id"]], 6)
    return ordered


def _dedupe_by_id(items: List[Dict]) -> List[Dict]:
    """Keep highest-similarity entry per chunk id (a text chunk lives in 3 spaces)."""
    seen: Dict[str, Dict] = {}
    for item in items:
        existing = seen.get(item["id"])
        if existing is None or item["similarity"] > existing["similarity"]:
            seen[item["id"]] = item
    return list(seen.values())


# ── MMR diversity & full-vault listing for BM25 ─────────────────

def list_referenced_doc_ids(vault: str) -> set:
    """Return the set of doc_ids that have at least one chunk in any space.

    Used by the orphan-upload sweeper to decide which files in
    uploads/<vault>/ are still backed by the vector store.
    """
    referenced: set = set()
    for col in _existing_subs(vault):
        try:
            data = col.get(include=["metadatas"])
        except Exception:
            continue
        for meta in (data.get("metadatas") or []):
            if not meta:
                continue
            doc_id = meta.get("doc_id")
            if doc_id:
                referenced.add(str(doc_id))
    return referenced


def list_all_chunks(vault: str) -> List[tuple]:
    """Return every chunk in a vault as (chunk_id, text, metadata), deduped by chunk id.
    Used by bm25_service to (re)build the lexical index."""
    seen: Dict[str, tuple] = {}
    for col in _existing_subs(vault):
        try:
            data = col.get(include=["metadatas", "documents"])
        except Exception:
            continue
        for i, cid in enumerate(data.get("ids", [])):
            if cid in seen:
                continue
            text = (data.get("documents") or [""])[i] if data.get("documents") else ""
            meta = (data.get("metadatas") or [{}])[i] if data.get("metadatas") else {}
            seen[cid] = (cid, text or "", meta or {})
    return list(seen.values())


def mmr_select(candidates: List[Dict], k: int = 10, lambda_: float = 0.5,
               relevance_key: str = "rerank_score") -> List[Dict]:
    """Maximal Marginal Relevance using TEXT Jaccard for diversity (space-agnostic).
    Relevance comes from the chosen `relevance_key` (e.g. rerank_score, or rrf_score, or similarity).
    """
    if not candidates or k <= 0:
        return []
    import re

    def tokens(s: str) -> set:
        return set(w.lower() for w in re.findall(r"\w+", s or "") if len(w) > 2)

    def jaccard(a: set, b: set) -> float:
        if not a or not b:
            return 0.0
        inter = len(a & b)
        return inter / max(1, len(a | b))

    tok_cache = [tokens(c.get("document") or "") for c in candidates]
    rels = [float(c.get(relevance_key, c.get("similarity", 0))) for c in candidates]
    # Normalize relevance to [0,1] so it's comparable to jaccard ∈ [0,1]
    rmin, rmax = min(rels), max(rels)
    span = (rmax - rmin) or 1.0
    rels_norm = [(r - rmin) / span for r in rels]

    selected: List[int] = []
    remaining = set(range(len(candidates)))
    while remaining and len(selected) < k:
        if not selected:
            i = max(remaining, key=lambda j: rels_norm[j])
        else:
            best_i, best_score = -1, -1e9
            for j in remaining:
                redundancy = max(jaccard(tok_cache[j], tok_cache[s]) for s in selected)
                score = lambda_ * rels_norm[j] - (1 - lambda_) * redundancy
                if score > best_score:
                    best_score, best_i = score, j
            i = best_i
        selected.append(i)
        remaining.remove(i)
    out = [candidates[i] for i in selected]
    for h in out:
        h.pop("embedding", None)
    return out
