"""
API routes — multimodal indexing and fan-out retrieval.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Request
from fastapi.responses import FileResponse
from typing import Optional, List, Dict
from datetime import datetime
import asyncio
import uuid
import os
import glob
import shutil

from app.models.schemas import ModalityType, detect_modality, MIME_TYPES, EXTENSION_TO_MODALITY
from app.services import perception_service, chroma_service, db_service, bm25_service, reranker_service, asr_service, image_captioner
from app.services.chunking_service import chunk_content, chunk_text, PDFExtractionError
from app.core.config import settings
from app.core.logger import app_logger as logger
from app.core.security import (
    generate_api_key, validate_request_auth, validate_admin_auth,
    validate_store_name, sanitize_filename,
)
from app.core.rate_limiter import limiter

router = APIRouter()

ALL_SPACES = ("image", "audio", "video")


# ── Helpers ───────────────────────────────────────────────────────

def _validate_file_size(file_bytes: bytes, filename: str) -> None:
    if len(file_bytes) > settings.max_file_size:
        raise HTTPException(
            status_code=413,
            detail=f"File '{filename}' exceeds maximum size of {settings.max_file_size // 1_000_000}MB",
        )


def _save_file(store_name: str, doc_id: str, filename: str, file_bytes: bytes) -> str:
    ext = os.path.splitext(filename)[1].lower()
    save_dir = os.path.join(settings.upload_dir, store_name)
    os.makedirs(save_dir, exist_ok=True)
    save_name = f"{doc_id}{ext}"
    save_path = os.path.join(save_dir, save_name)
    with open(save_path, "wb") as f:
        f.write(file_bytes)
    return f"/api/files/{store_name}/{save_name}"


async def _index_text_chunk(vault: str, chunk_id: str, text: str, base_meta: Dict) -> None:
    """Embed a single text chunk into all 3 spaces. Kept for backward compatibility."""
    await _index_text_chunks(vault, [{"chunk_id": chunk_id, "text": text, "base_meta": base_meta}])


async def _index_text_chunks(vault: str, items: List[Dict]) -> None:
    """Batch-embed many text chunks into all 3 spaces.

    Each item: {"chunk_id": str, "text": str, "base_meta": Dict}
    Writes 1 chroma_service.add_chunks call per space (3 total) with all chunks.
    """
    if not items:
        return
    texts = [it["text"] for it in items]
    # PE inference is sync + heavy — run off the event loop
    embeds_per_text = await asyncio.to_thread(perception_service.encode_text_all_batch, texts)

    for space in ALL_SPACES:
        rows = [
            {
                "id": items[i]["chunk_id"],
                "embedding": embeds_per_text[i][space],
                "metadata": {**items[i]["base_meta"], "space": space},
                "text": texts[i],
            }
            for i in range(len(items))
        ]
        chroma_service.add_chunks(vault, space, rows)


# ── Health ────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    try:
        memory = perception_service.memory_stats()
    except Exception as e:
        memory = {"error": str(e)}
    return {
        "status": "healthy" if perception_service.is_ready() and chroma_service.is_ready() else "degraded",
        "perception_encoder": perception_service.is_ready(),
        "chromadb": chroma_service.is_ready(),
        "memory": memory,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ── Vector Stores ─────────────────────────────────────────────────

@router.post("/stores")
@limiter.limit(settings.rate_limit_stores)
async def create_store(request: Request, name: str = Form(...), description: str = Form("")):
    """Create a new vault. Returns a one-time API key."""
    validate_admin_auth(request)
    validate_store_name(name)
    try:
        plaintext_key, hashed_key = generate_api_key()
        store = chroma_service.create_collection(
            name, description,
            extra_metadata={"api_key_hash": hashed_key},
        )
        try:
            db_service.create_vault(name, description)
        except ValueError:
            pass  # already exists in SQLite (re-creation of chroma-only vault)
        return {
            "success": True,
            "store": store,
            "api_key": plaintext_key,
            "warning": "Save this API key now. It cannot be retrieved later.",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/stores")
async def list_stores(request: Request):
    validate_admin_auth(request)
    stores = chroma_service.list_collections()
    # Enrich with file_count from SQLite (chroma's count is total embeddings, not files)
    try:
        sqlite_vaults = {v["name"]: v for v in db_service.list_vaults()}
    except Exception:
        sqlite_vaults = {}
    for s in stores:
        meta = sqlite_vaults.get(s["name"])
        s["file_count"] = meta["file_count"] if meta else 0
        if meta and meta.get("description") and not s.get("metadata", {}).get("description"):
            s.setdefault("metadata", {})["description"] = meta["description"]
    return {"stores": stores, "total": len(stores)}


@router.get("/stores/{name}")
async def get_store(request: Request, name: str):
    validate_request_auth(request, name)
    store = chroma_service.get_collection(name)
    if not store:
        raise HTTPException(status_code=404, detail=f"Store '{name}' not found")
    return store


@router.post("/stores/{name}/rotate-key")
@limiter.limit(settings.rate_limit_stores)
async def rotate_store_key(request: Request, name: str):
    """Issue a new API key for a vault, replacing the old one. Returns plaintext."""
    validate_request_auth(request, name)
    if not chroma_service.get_collection(name):
        raise HTTPException(status_code=404, detail=f"Store '{name}' not found")
    plaintext, hashed = generate_api_key()
    if not chroma_service.update_api_key_hash(name, hashed):
        raise HTTPException(status_code=500, detail="Failed to rotate key")
    return {"success": True, "store": name, "api_key": plaintext}


@router.delete("/stores/{name}")
async def delete_store(request: Request, name: str):
    validate_request_auth(request, name)
    if chroma_service.delete_collection(name):
        store_dir = os.path.join(settings.upload_dir, name)
        if os.path.exists(store_dir):
            shutil.rmtree(store_dir, ignore_errors=True)
        return {"success": True, "message": f"Deleted '{name}'"}
    raise HTTPException(status_code=404, detail=f"Store '{name}' not found")


# ── Document Management ──────────────────────────────────────────

@router.delete("/stores/{name}/documents/{doc_id}")
async def delete_document(request: Request, name: str, doc_id: str):
    validate_request_auth(request, name)
    if not chroma_service.get_collection(name):
        raise HTTPException(status_code=404, detail=f"Store '{name}' not found")

    count = chroma_service.delete_document(name, doc_id)
    if count == 0:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")

    pattern = os.path.join(settings.upload_dir, name, f"{doc_id}.*")
    for filepath in glob.glob(pattern):
        os.remove(filepath)

    return {"success": True, "deleted_chunks": count, "doc_id": doc_id}


# ── Embed ─────────────────────────────────────────────────────────

@router.post("/embed")
@limiter.limit(settings.rate_limit_embed)
async def embed(
    request: Request,
    vector_store: str = Form(...),
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    """Embed text or a file into a vault."""
    validate_request_auth(request, vector_store)

    if not text and not file:
        raise HTTPException(status_code=400, detail="Provide either 'text' or 'file'")

    if not chroma_service.get_collection(vector_store):
        raise HTTPException(status_code=404, detail=f"Store '{vector_store}' not found")

    doc_id = str(uuid.uuid4())

    try:
        if text:
            return await _embed_text(vector_store, doc_id, text)
        else:
            return await _embed_file(vector_store, doc_id, file)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Embedding failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _embed_text(vault: str, doc_id: str, text: str) -> dict:
    """Embed raw text input — chunked and indexed into all 3 spaces."""
    chunks_text = chunk_text(text) if len(text) > settings.chunk_size else [text]

    timestamp = datetime.utcnow().isoformat()
    items = [
        {
            "chunk_id": f"{doc_id}_chunk_{i}",
            "text": ct,
            "base_meta": {
                "modality": "text",
                "filename": "text_input",
                "doc_id": doc_id,
                "chunk_index": i,
                "total_chunks": len(chunks_text),
                "timestamp": timestamp,
            },
        }
        for i, ct in enumerate(chunks_text)
    ]
    await _index_text_chunks(vault, items)

    try:
        rec = db_service.record_file(vault, "text_input", "text/plain", "text", doc_id, len(text.encode("utf-8")))
        db_service.update_file_status(rec["id"], "indexed", chunk_count=len(chunks_text))
    except Exception as _e:
        logger.warning(f"db_service.record_file failed: {_e}")

    return {
        "success": True,
        "id": doc_id,
        "modality": "text",
        "filename": "text_input",
        "chunks": len(chunks_text),
        "dimensions": perception_service.EMBEDDING_DIM,
        "store": vault,
    }


async def _embed_file(vault: str, doc_id: str, file: UploadFile) -> dict:
    """Dispatch a file to the right encoder + space."""
    modality, mime_type = detect_modality(file.filename)
    if not modality or not mime_type:
        ext = os.path.splitext(file.filename)[1].lower()
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: '{ext}'. Supported: {list(MIME_TYPES.keys())}",
        )

    filename = sanitize_filename(file.filename)
    file_bytes = await file.read()
    _validate_file_size(file_bytes, filename)
    file_url = _save_file(vault, doc_id, filename, file_bytes)
    ext = os.path.splitext(filename)[1].lower()

    base_meta = {
        "modality": modality.value,
        "filename": filename,
        "mime_type": mime_type,
        "file_url": file_url,
        "doc_id": doc_id,
        "size_bytes": len(file_bytes),
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Chunkable text-bearing modalities → text path
    try:
        chunks = chunk_content(file_bytes, filename, modality.value)
    except PDFExtractionError as e:
        # Surface a clear reason; record the failure on the file row.
        try:
            rec = db_service.record_file(vault, filename, mime_type, modality.value, doc_id, len(file_bytes))
            db_service.update_file_status(rec["id"], "failed", error=str(e))
        except Exception as _e:
            logger.warning(f"db_service failed-row write failed: {_e}")
        raise HTTPException(status_code=400, detail=f"PDF unreadable: {e}")

    if chunks:
        items = []
        for i, chunk in enumerate(chunks):
            meta = {**base_meta, "chunk_index": i, "total_chunks": len(chunks)}
            if "page_numbers" in chunk:
                meta["page_numbers"] = chunk["page_numbers"]
            if "section" in chunk:
                meta["section"] = chunk["section"]
            items.append({
                "chunk_id": f"{doc_id}_chunk_{i}",
                "text": chunk["text"],
                "base_meta": meta,
            })
        await _index_text_chunks(vault, items)

        try:
            rec = db_service.record_file(vault, filename, mime_type, modality.value, doc_id, len(file_bytes))
            db_service.update_file_status(rec["id"], "indexed", chunk_count=len(chunks))
        except Exception as _e:
            logger.warning(f"db_service.record_file failed: {_e}")

        return {
            "success": True,
            "id": doc_id,
            "modality": modality.value,
            "filename": filename,
            "chunks": len(chunks),
            "dimensions": perception_service.EMBEDDING_DIM,
            "store": vault,
            "file_url": file_url,
        }

    # Non-chunkable: image, audio, video, or text fallback.
    # NOTE: deliberately don't set document_text here — let chroma_service's
    # _document_text_for_chunk() generate a humanized form from the filename
    # so the cross-encoder reranker has real content to score.
    chunk_id = f"{doc_id}_chunk_0"
    base_meta.update({"chunk_index": 0, "total_chunks": 1})

    if modality == ModalityType.IMAGE:
        # Caption once per image — gives the cross-encoder reranker real prose
        # to score against (the synthesized "image eiffel tower" loses to any
        # speech transcript on length bias).
        caption = await asyncio.to_thread(image_captioner.caption_image, file_bytes)

        # Tile the image: full + 4 quadrants → 5 vectors. Region-level recall
        # for queries targeting a specific element of a busy/wide image.
        tiles = await asyncio.to_thread(perception_service.encode_image_tiles, file_bytes)
        for i, t in enumerate(tiles):
            is_full = t["region"] == "full"
            tmeta = {
                **base_meta,
                "chunk_index": i,
                "total_chunks": len(tiles),
                "region": t["region"],
                "bbox": str(t["bbox"]),  # chroma metadata only accepts scalars
                "is_full_image": is_full,
            }
            # Only the full-image chunk gets the caption — quadrant captions
            # would be misleading without a region-aware captioner.
            if is_full and caption:
                tmeta["document_text"] = caption
                tmeta["caption"] = caption
            cid = f"{doc_id}_chunk_{i}"
            chroma_service.add_embedding(vault, "image", cid, t["embedding"], tmeta)
        n_chunks = len(tiles)
        if caption:
            logger.info(f"image captioned: {filename!r} → {caption!r}")
    elif modality == ModalityType.AUDIO:
        # Acoustic chunks: each window is a bounded time-range, retrievable via PE-AV.
        # Good for non-speech queries ("thunder", "piano music").
        windows = await asyncio.to_thread(
            perception_service.encode_audio_windows, file_bytes, ext or ".wav"
        )
        for i, w in enumerate(windows):
            wmeta = {
                **base_meta,
                "chunk_index": i,
                "total_chunks": len(windows),
                "start_sec": w["start_sec"],
                "end_sec": w["end_sec"],
                "audio_track": "acoustic",
            }
            cid = f"{doc_id}_chunk_{i}"
            chroma_service.add_embedding(vault, "audio", cid, w["embedding"], wmeta)

        # Speech transcription: PE-AV doesn't read the words. Transcribe the
        # audio and write each segment ONLY to the audio space (via
        # text-for-audio projection) so spoken content is searchable without
        # polluting image/video retrieval. BM25 still picks up the literal
        # text for lexical matching.
        transcript = await asyncio.to_thread(asr_service.transcribe_audio, file_bytes, ext or ".wav")
        n_speech = 0
        if transcript:
            speech_texts = [(seg.get("text") or "").strip() for seg in transcript]
            speech_texts = [t for t in speech_texts if len(t) >= 8]
            if speech_texts:
                # Batch text-for-audio embeddings (one network call instead of N)
                embs = await asyncio.to_thread(
                    perception_service.encode_text_for_audio_batch, speech_texts
                )
                kept_segments = [seg for seg, t in zip(transcript, [(s.get("text") or "").strip() for s in transcript]) if len(t) >= 8]
                for j, (seg, text, emb) in enumerate(zip(kept_segments, speech_texts, embs)):
                    cid = f"{doc_id}_speech_{j}"
                    smeta = {
                        **base_meta,
                        "audio_track": "speech",
                        "chunk_index": len(windows) + j,
                        "total_chunks_speech": len(speech_texts),
                        "start_sec": seg.get("start_sec"),
                        "end_sec": seg.get("end_sec"),
                        "transcript": text,
                    }
                    chroma_service.add_chunks(vault, "audio", [{
                        "id": cid,
                        "embedding": emb,
                        "metadata": {**smeta, "space": "audio"},
                        "text": text,
                    }])
                n_speech = len(speech_texts)
        n_chunks = len(windows) + n_speech
        logger.info(f"audio indexed: {len(windows)} acoustic + {n_speech} speech chunks for {filename}")
    elif modality == ModalityType.VIDEO:
        # Sliding-window video — same shape as audio: each chunk is a bounded
        # time-range. Long clips become individually retrievable segments.
        windows = await asyncio.to_thread(
            perception_service.encode_video_windows, file_bytes, ext or ".mp4"
        )
        for i, w in enumerate(windows):
            wmeta = {
                **base_meta,
                "chunk_index": i,
                "total_chunks": len(windows),
                "start_sec": w["start_sec"],
                "end_sec": w["end_sec"],
            }
            cid = f"{doc_id}_chunk_{i}"
            chroma_service.add_embedding(vault, "video", cid, w["embedding"], wmeta)
        n_chunks = len(windows)
    elif modality == ModalityType.TEXT:
        # Text fallback (e.g. empty chunker result); index once
        text_content = file_bytes.decode("utf-8", errors="replace")
        base_meta["document_text"] = text_content[:1000]
        await _index_text_chunk(vault, chunk_id, text_content[:settings.chunk_size], base_meta)
        n_chunks = 1
    else:
        raise HTTPException(status_code=400, detail=f"No encoder for modality '{modality.value}'")

    try:
        rec = db_service.record_file(vault, filename, mime_type, modality.value, doc_id, len(file_bytes))
        db_service.update_file_status(rec["id"], "indexed", chunk_count=n_chunks)
    except Exception as _e:
        logger.warning(f"db_service.record_file failed: {_e}")

    return {
        "success": True,
        "id": doc_id,
        "modality": modality.value,
        "filename": filename,
        "chunks": n_chunks,
        "dimensions": perception_service.EMBEDDING_DIM,
        "store": vault,
        "file_url": file_url,
    }


@router.post("/embed/batch")
@limiter.limit(settings.rate_limit_embed)
async def embed_batch(
    request: Request,
    vector_store: str = Form(...),
    files: List[UploadFile] = File(...),
):
    """Embed multiple files at once."""
    validate_request_auth(request, vector_store)

    if not chroma_service.get_collection(vector_store):
        raise HTTPException(status_code=404, detail=f"Store '{vector_store}' not found")

    results = []
    for file in files:
        try:
            doc_id = str(uuid.uuid4())
            result = await _embed_file(vector_store, doc_id, file)
            results.append({
                "filename": result["filename"],
                "success": True,
                "id": result["id"],
                "modality": result["modality"],
                "chunks": result["chunks"],
            })
        except HTTPException as e:
            results.append({"filename": file.filename, "success": False, "error": e.detail})
        except Exception as e:
            results.append({"filename": file.filename, "success": False, "error": str(e)})

    succeeded = sum(1 for r in results if r.get("success"))
    return {"success": True, "total": len(files), "succeeded": succeeded, "results": results}


# ── Retrieval pipeline ──────────────────────────────────────────

async def _smart_text_retrieve(
    vault: str,
    query: str,
    top_k: int,
    min_similarity: float = 0.0,
    *,
    use_bm25: bool = True,
    use_mmr: bool = True,
    mmr_lambda: float = 0.5,
    use_rerank: bool = True,
    pool_size: int = 50,
    rrf_k: int = 60,
) -> List[Dict]:
    """Pipeline: dense × 3 PE spaces + BM25 → RRF → cross-encoder rerank → MMR (text diversity) → top-K."""
    embeds = await asyncio.to_thread(perception_service.encode_text_all, query)
    per_space = {}
    for space, embed in embeds.items():
        # Speech-derived chunks live in the audio space but are text-for-audio
        # projections of transcript text. Comparing those to a text query in
        # the same projection is text-text in a non-text space — unreliable.
        # Exclude them from dense retrieval; BM25 still catches them lexically
        # via list_all_chunks below.
        where = {"audio_track": {"$ne": "speech"}} if space == "audio" else None
        hits = chroma_service.search_space_pool(vault, space, embed, pool_size,
                                                include_embeddings=False,
                                                where=where)
        for h in hits:
            h["space"] = space
        per_space[space] = hits

    if use_bm25:
        bm25_hits = bm25_service.search(
            vault, query,
            chunks_provider=chroma_service.list_all_chunks,
            n_results=pool_size,
        )
        for h in bm25_hits:
            h["space"] = "bm25"
        per_space["bm25"] = bm25_hits

    merged = chroma_service._rrf_merge(per_space, k=rrf_k)
    if min_similarity > 0:
        merged = [h for h in merged if h.get("similarity", 0) >= min_similarity]
    if not merged:
        return []

    # Cross-encoder rerank over a generous candidate set first
    rerank_pool = max(top_k * 4, 20)
    if use_rerank and reranker_service.is_ready():
        try:
            merged = await asyncio.to_thread(
                reranker_service.rerank, query, merged[:rerank_pool], top_k=rerank_pool
            )
        except Exception as e:
            logger.warning(f"Reranker failed, falling back to RRF order: {e}")
            merged = merged[:rerank_pool]
    else:
        merged = merged[:rerank_pool]

    # MMR diversifies on the reranker-ordered list using text overlap
    if use_mmr:
        relevance_key = "rerank_score" if (use_rerank and reranker_service.is_ready()) else "rrf_score"
        merged = chroma_service.mmr_select(merged, k=top_k, lambda_=mmr_lambda,
                                           relevance_key=relevance_key)
    else:
        merged = merged[:top_k]
    return merged


# ── Search ────────────────────────────────────────────────────────

@router.post("/search")
@limiter.limit(settings.rate_limit_search)
async def search(
    request: Request,
    vector_store: str = Form(...),
    query: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    n_results: int = Form(10),
    min_similarity: float = Form(0.0),
):
    """Search a vault by text or by file (modality auto-detected)."""
    validate_request_auth(request, vector_store)

    if not query and not file:
        raise HTTPException(status_code=400, detail="Provide either 'query' (text) or 'file'")

    if not chroma_service.get_collection(vector_store):
        raise HTTPException(status_code=404, detail=f"Store '{vector_store}' not found")

    try:
        if query:
            results = await _smart_text_retrieve(vector_store, query, n_results, min_similarity)
            query_info = {"type": "text", "query": query}
        else:
            modality, mime_type = detect_modality(file.filename)
            if not modality or not mime_type:
                raise HTTPException(status_code=400, detail="Unsupported file type")

            file_bytes = await file.read()
            ext = os.path.splitext(file.filename)[1].lower()

            if modality == ModalityType.IMAGE:
                emb = await asyncio.to_thread(perception_service.encode_image, file_bytes)
                results = chroma_service.search_space(vector_store, "image", emb, n_results, min_similarity)
            elif modality == ModalityType.AUDIO:
                emb = await asyncio.to_thread(perception_service.encode_audio, file_bytes, ext=ext or ".wav")
                results = chroma_service.search_space(vector_store, "audio", emb, n_results, min_similarity)
            elif modality == ModalityType.VIDEO:
                emb = await asyncio.to_thread(perception_service.encode_video, file_bytes, ext=ext or ".mp4")
                results = chroma_service.search_space(vector_store, "video", emb, n_results, min_similarity)
            elif modality == ModalityType.TEXT:
                text_content = file_bytes.decode("utf-8", errors="replace")[:settings.chunk_size]
                results = await _smart_text_retrieve(vector_store, text_content, n_results, min_similarity)
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported query modality '{modality.value}'")

            query_info = {"type": modality.value, "filename": file.filename}

        return {
            "success": True,
            "query": query_info,
            "store": vector_store,
            "count": len(results),
            "results": results,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── RAG Retrieve ──────────────────────────────────────────────────

@router.post("/retrieve")
@limiter.limit(settings.rate_limit_search)
async def retrieve(request: Request):
    """RAG-optimized retrieval. JSON body: {store, query, top_k, min_similarity}."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    store_name = body.get("store")
    query = body.get("query")
    top_k = body.get("top_k", 5)
    min_similarity = body.get("min_similarity", 0.0)

    if not store_name or not query:
        raise HTTPException(status_code=400, detail="Both 'store' and 'query' are required")

    validate_request_auth(request, store_name)

    if not chroma_service.get_collection(store_name):
        raise HTTPException(status_code=404, detail=f"Store '{store_name}' not found")

    try:
        results = await _smart_text_retrieve(store_name, query, top_k, min_similarity)

        context = []
        for r in results:
            meta = r.get("metadata", {})
            item = {
                "text": r.get("document", ""),
                "source": meta.get("filename", "unknown"),
                "modality": meta.get("modality", ""),
                "matched_space": r.get("space", ""),
                "relevance": r.get("similarity", 0),
            }
            if "page_numbers" in meta:
                item["page"] = meta["page_numbers"]
            if "section" in meta:
                item["section"] = meta["section"]
            if "chunk_index" in meta:
                item["chunk"] = meta["chunk_index"]
            if "file_url" in meta:
                item["file_url"] = meta["file_url"]
            context.append(item)

        return {"context": context}
    except Exception as e:
        logger.exception(f"Retrieve failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Auth-gated file serving ──────────────────────────────────────

@router.get("/files/{store_name}/{filename}")
async def get_file(request: Request, store_name: str, filename: str):
    """Serve an uploaded file. Requires the same auth as the parent vault.

    Accepts either the X-API-Key header or `?api_key=...` (for <img>/<video>
    src attributes that can't set headers).
    """
    validate_request_auth(request, store_name)

    # Strict path containment: resolve realpath and check it stays inside upload_dir
    base_dir = os.path.realpath(settings.upload_dir)
    target = os.path.realpath(os.path.join(base_dir, store_name, filename))
    if not (target == base_dir or target.startswith(base_dir + os.sep)):
        raise HTTPException(status_code=400, detail="Invalid file path")
    if not os.path.isfile(target):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(target)


# ── Supported Formats ────────────────────────────────────────────

@router.get("/formats")
async def get_formats():
    by_modality = {}
    for ext, modality in EXTENSION_TO_MODALITY.items():
        by_modality.setdefault(modality.value, []).append(ext)
    return {"formats": by_modality}


# ── Vault Metadata (SQLite) ──────────────────────────────────────

@router.get("/vaults")
async def list_vaults_endpoint(request: Request):
    """Rich list of vaults with description, timestamps, and file_count."""
    validate_admin_auth(request)
    vaults = db_service.list_vaults()
    return {"vaults": vaults, "total": len(vaults)}


@router.get("/vaults/{name}")
async def get_vault_endpoint(request: Request, name: str):
    """Full detail for a single vault (includes file_count)."""
    validate_request_auth(request, name)
    vault = db_service.get_vault(name)
    if not vault:
        raise HTTPException(status_code=404, detail=f"Vault '{name}' not found")
    return vault


@router.get("/vaults/{name}/files")
async def list_vault_files_endpoint(request: Request, name: str, status: Optional[str] = None):
    """List files in a vault, optionally filtered by status."""
    validate_request_auth(request, name)
    if not db_service.get_vault(name):
        raise HTTPException(status_code=404, detail=f"Vault '{name}' not found")
    try:
        files = db_service.list_files(name, status=status)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    return {"vault": name, "status_filter": status, "count": len(files), "files": files}


# ── Orphan upload sweep ──────────────────────────────────────────

def _sweep_orphans(vault: str, dry_run: bool = False) -> Dict:
    """Delete files in uploads/<vault>/ whose doc_id has no chunks in Chroma.

    Files are stored as `<doc_id><ext>` (see _save_file), so we strip the
    extension to recover the doc_id and compare against the live set in
    the vector store. Returns counts + the list of removed/orphan paths.
    """
    vault_dir = os.path.join(settings.upload_dir, vault)
    if not os.path.isdir(vault_dir):
        return {"vault": vault, "scanned": 0, "orphans": 0, "removed": [], "kept": 0}

    referenced = chroma_service.list_referenced_doc_ids(vault)
    removed: List[str] = []
    kept = 0
    scanned = 0

    for entry in os.listdir(vault_dir):
        full = os.path.join(vault_dir, entry)
        if not os.path.isfile(full):
            continue
        scanned += 1
        doc_id = os.path.splitext(entry)[0]
        if doc_id in referenced:
            kept += 1
            continue
        # Orphan
        if not dry_run:
            try:
                os.remove(full)
            except OSError as e:
                logger.warning(f"orphan sweep: could not remove {full}: {e}")
                continue
        removed.append(entry)

    return {
        "vault": vault,
        "scanned": scanned,
        "orphans": len(removed),
        "removed": removed,
        "kept": kept,
        "dry_run": dry_run,
    }


def sweep_all_vaults_orphans() -> Dict:
    """Run the orphan sweep across every vault on disk. Best-effort; logs only."""
    base = settings.upload_dir
    if not os.path.isdir(base):
        return {"vaults": 0, "total_orphans": 0}
    total = 0
    n_vaults = 0
    for entry in os.listdir(base):
        full = os.path.join(base, entry)
        if not os.path.isdir(full):
            continue
        try:
            res = _sweep_orphans(entry, dry_run=False)
        except Exception as e:
            logger.warning(f"orphan sweep failed for vault {entry!r}: {e}")
            continue
        n_vaults += 1
        total += res["orphans"]
        if res["orphans"]:
            logger.info(f"orphan sweep: vault={entry!r} removed={res['orphans']} kept={res['kept']}")
    return {"vaults": n_vaults, "total_orphans": total}


@router.post("/admin/orphans/{vault_name}")
async def sweep_vault_orphans_endpoint(request: Request, vault_name: str, dry_run: bool = False):
    """Admin: delete uploaded files in a vault whose chunks are gone from Chroma.

    `?dry_run=true` reports what would be removed without touching disk.
    """
    validate_admin_auth(request)
    if not chroma_service.get_collection(vault_name):
        raise HTTPException(status_code=404, detail=f"Store '{vault_name}' not found")
    return _sweep_orphans(vault_name, dry_run=dry_run)


@router.post("/vaults/{name}/files/{file_id}/retry")
async def retry_vault_file_endpoint(request: Request, name: str, file_id: str):
    """Mark a failed file as queued so it can be retried later (v1: status flip only)."""
    validate_request_auth(request, name)
    if not db_service.get_vault(name):
        raise HTTPException(status_code=404, detail=f"Vault '{name}' not found")

    file_row = db_service.get_file(file_id)
    if not file_row:
        raise HTTPException(status_code=404, detail=f"File '{file_id}' not found")

    if not db_service.update_file_status(file_id, "queued", error=""):
        raise HTTPException(status_code=500, detail="Failed to update file status")

    return {"success": True, "file_id": file_id, "status": "queued"}
